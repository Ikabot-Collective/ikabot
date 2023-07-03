import gettext
from ikabot.command_line import menu
from ikabot.config import *
from ikabot.helpers.botComm import sendToBot
from ikabot.helpers.pedirInfo import *
from ikabot.function.trainArmy import generateArmyData, getBuildingInfo
from ikabot.helpers.planRoutes import executeRoutes
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.naval import getAvailableShips



t = gettext.translation('buyResources', localedir, languages=languages, fallback=True)
_ = t.gettext

def get_city_military_data(session, city_id):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int
    
    returns
    -------
    data : dict
    """
    params = {
        "view": "cityMilitary",
        "activeTab": "tabUnits",
        "cityId": city_id,
        "currentTab": "tabUnits",
        "currentCityId": city_id,
        "templateView": "cityMilitary",
        "actionRequest": actionRequest,
        "ajax": "1"
    }
    data = session.post(params=params)
    data = json.loads(data, strict=False)
    return data[1][1][1]

def extract_tooltips_and_values(data):
    tooltips = re.findall(r'<div class="tooltip">(.*?)</div>', data)
    values = re.findall(r'<td>\s*([\d.-]+)\s*</td>', data)
    return tooltips, values

def calculate_totals(tooltips, values):
    total_units = 0
    total_ships = 0

    desc_value_dict = {}

    for i, (tooltip, value) in enumerate(zip(tooltips, values)):
        desc_value_dict.setdefault(tooltip, []).append(value)

        if value.isdigit() and i <= 14:
            total_units += int(value)
        elif value.isdigit():
            total_ships += int(value)

    return desc_value_dict, total_units, total_ships

def get_army_available(session, type_army, destination_city_id, origin_city_id, event):
    params = {
        "view": "deployment",
        "deploymentType": "army" if type_army else "fleet",
        "destinationCityId": destination_city_id,
        "backgroundView": "city",
        "currentCityId": origin_city_id,
        "actionRequest": actionRequest,
        "ajax": 1
    }

    data = session.post(params=params)
    amount_results = re.findall(r'<div class=\\"amount\\">(.*?)<\\/div>', data)
    
    if type_army:
        army_results = re.findall(r'name=\\"cargo_army_([^\\]+)_upkeep\\"\\n\s+value=\\"([^\\"]+)\\"', data)
        weight_total_ships = int(getAvailableShips(session)) * 500 if type_army else 0
        weight_results = re.findall(r'<div class=\\"weight\\">(.*?)<\\/div>', data)
    else:
        army_results = re.findall(r'name=\\"cargo_fleet_([^\\]+)_upkeep\\"\\n\s+value=\\"([^\\"]+)\\"', data)


    army_available = {}
    weight_total_army = 0

    if army_results:
        for i, result in enumerate(army_results):
            army_code = result[0]
            army = "cargo_{}_{}_upkeep".format("army" if type_army else "fleet", army_code)
            army_only = "cargo_{}_{}".format("army" if type_army else "fleet", army_code)
            upkeep = result[1]
            quantity = amount_results[i]
            army_available[army] = upkeep
            army_available[army_only] = quantity
            if type_army and weight_results and int(weight_results[i]) > 0:
                weight_total_army += int(quantity) * int(weight_results[i])
    
        if type_army and weight_total_army > weight_total_ships:
            banner()
            print('Not enough ships to transport all the units!')
            enter()
            return None
        return army_available
    return None


def send_army(session, origin_city, destination_city, type_army, army_available):
    params = {
        "action": "transportOperations",
        "function": "deployArmy" if type_army else "deployFleet",
        "actionRequest": actionRequest,
        "islandId": destination_city['islandId'],
        "destinationCityId": destination_city['id'],
        "deploymentType": "army" if type_army else "fleet",
        "backgroundView": "city",
        "currentCityId": origin_city['id'],
        "templateView": "deployment",
        "ajax": 1
    }

    for army in army_available:
        params[army] = army_available[army]

    session.post(params=params)

def army_station(session,event, stdin_fd, predetermined_input):
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    type_army = True
    try:
        banner()

        ids, cities = getIdsOfCities(session)
        army = {}
        print('Total:')
        print('{:>19}|{:>19}|{:>19}|'.format('', 'Units', 'Ships'))

        for city_id in cities:
            city = cities[city_id]
            data = get_city_military_data(session, city['id'])
            desc, values = extract_tooltips_and_values(data)
            army, total_units, total_ships = calculate_totals(desc, values)
            
            print('{:>19}|{:>19}|{:>19}|'.format(city['name'], total_units, total_ships))
        
        print()
        print(_('(0) Back'))
        print(_('(1) Move troops'))
        print(_('(2) Move ships'))
        print(_('(3) Move all ground units to a city.'))
        print(_('(4) Move all maritime units to a city.'))
        print(_('(5) Move all units to a city.'))
        
        selected = read(min=0, max=5, digit=True)
        if selected == 0:
            menu(session)
            return
        elif selected in (1, 2):
            print('Origin city:')
            origin_city = chooseCity(session)
            print()
            print('Destination city:')
            destination_city = chooseCity(session)
            if origin_city['id'] == destination_city['id']:
                banner()
                print('The city of origin and the destination city cannot be the same!')
                enter()
                event.set()
            else:
                type_army = selected == 1
                army_available = get_army_available(session, type_army, destination_city['id'], origin_city['id'], event)
                if army_available != None:
                    send_army(session, origin_city, destination_city, type_army, army_available)
                    print('Army sent!')
                    enter()
                    event.set()
                else:
                    print()
                    print('No {} units available in {}.'.format('ground' if type_army else 'maritime', origin_city['name']))
                    enter()
                    event.set()
        elif selected in (3,4,5):
            print('Destination city:')
            destination_city = chooseCity(session)
            ids, cities = getIdsOfCities(session)
            
            if selected in (3,5):
                type_army = True
                for city_id in cities:
                    if city_id != destination_city['id']:
                        city = cities[city_id]
                        army_available = get_army_available(session, type_army, destination_city['id'], city['id'], event)
                        if army_available != None:
                            send_army(session, city, destination_city, type_army, army_available)
                        else:
                            print('No ground units available in {}.'.format(city['name']))
            if selected in (4,5):
                type_army = False
                for city_id in cities:
                    if city_id != destination_city['id']:
                        city = cities[city_id]
                        army_available = get_army_available(session, type_army, destination_city['id'], city['id'], event)
                        if army_available != None:
                            send_army(session, city, destination_city, type_army, army_available)
                        else:
                            print('No maritime units available in {}.'.format(city['name']))
            enter()
            event.set()               
    except KeyboardInterrupt:
        event.set()
        return  