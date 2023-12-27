#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback

from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getIsland
from ikabot.helpers.gui import enter
from ikabot.helpers.pedirInfo import getIslandsIds
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import wait, getDateTime, decodeUnicodeEscape

t = gettext.translation('searchForIslandSpaces', localedir, languages=languages, fallback=True)
_ = t.gettext


def searchForIslandSpaces(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
        if checkTelegramData(session) is False:
            event.set()
            return
        banner()

        print('Do you want to search for spaces on your islands or a specific set of islands?')
        print('(0) Exit')
        print('(1) Search all islands I have colonised')
        print('(2) Search a specific set of islands')
        choice = read(min=0, max=2)
        island_ids = []
        if choice == 0:
            event.set()
            return
        elif choice == 2:
            banner()
            print('Insert the coordinates of each island you want searched like so: X1:Y1, X2:Y2, X3:Y3...')
            coords_string = read()
            coords_string = coords_string.replace(' ', '')
            coords = coords_string.split(',')
            for coord in coords:
                coord = '&xcoord=' + coord
                coord = coord.replace(':', '&ycoord=')
                html = session.get('view=island' + coord)
                island = getIsland(html)
                island_ids.append(island['id'])
        else:
            pass

        banner()
        print('How frequently should the islands be searched in minutes (minimum is 3)?')
        waiting_minutes = read(min=3, digit=True)
        banner()
        print('Do you wish to be notified when a fight breaks out and stops on a city on these islands? (Y|N)')
        fights = read(values=['y', 'Y', 'n', 'N'])
        banner()
        print(_('I will search for changes in the selected islands'))
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = '\nI search for new spaces every {} minutes\n'.format(waiting_minutes)
    setInfoSignal(session, info)
    try:
        __execute_monitoring(session, island_ids, waiting_minutes, fights.lower() == 'y')
    except Exception as e:
        msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def __execute_monitoring(session, specified_island_ids, waiting_minutes, check_fights):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    specified_island_ids : list[dict]
        A list containing island objects which should be searched, if an empty list is passed, all the user's colonised islands are searched
    waiting_minutes : int
        The time in minutes between two consecutive searches
    check_fights : bool
        Indicates whether to scan for fight activity on islands
    """

    # this dict will contain all the cities from each island
    # as they were in last scan
    # {islandId: {cityId: city}}
    cities_before_per_island = {}

    while True:
        islands_ids = specified_island_ids
        if not islands_ids:
            # this is done inside the loop because the user may have colonized
            # a city in a new island
            islands_ids = getIslandsIds(session)

        for island_id in islands_ids:
            html = session.get(island_url + island_id)
            island = getIsland(html)
            # cities in the current island
            cities_now = __extract_cities(island)

            if island_id in cities_before_per_island:
                __compare_island_cities(
                    session,
                    cities_before=cities_before_per_island[island_id],
                    cities_now=cities_now,
                    check_fights=check_fights
                )

            # update cities_before_per_island for the current island
            cities_before_per_island[island_id] = dict(cities_now)

        session.setStatus(f'Checked islands {str([int(i) for i in islands_ids]).replace(" ","")} @ {getDateTime()[-8:]}')
        wait(waiting_minutes * 60)

def __extract_cities(island):
    '''
    Extract the cities from island
    :param island: dict[]
    :return: dict[dict] cityId -> city
    '''
    _res = {}

    _island_name = decodeUnicodeEscape(island['name'])
    for city in island['cities']:
        if city['type'] != 'city':
            continue

        city['islandX'] = island['x']
        city['islandY'] = island['y']
        city['tradegood'] = island['tradegood']
        city['material'] = materials_names[island['tradegood']]
        city['islandName'] = _island_name
        city['cityName'] = decodeUnicodeEscape(city['name'])
        city['ownerName'] = decodeUnicodeEscape(city['Name'])
        if city['AllyId'] > 0:
            city['allianceName'] = decodeUnicodeEscape(city['AllyTag'])
            city['hasAlliance'] = True
            city['player'] = "{} [{}]".format(city['ownerName'], city['allianceName'])
        else:
            city['alliance'] = ''
            city['hasAlliance'] = False
            city['player'] = city['ownerName']

        _res[city['id']] = city

    return _res

def __compare_island_cities(session, cities_before, cities_now, check_fights):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    cities_before : dict[dict]
        A dict of cities on the island on the previous check
    cities_now : dict[dict]
        A dict of cities on the island on the current check
    check_fights : bool
        Indicates whether to scan for fight activity on islands
    """
    __island_info = ' on [{islandX}:{islandY}] {islandName} ({material})'

    # someone disappeared
    for disappeared_id in __search_additional_keys(cities_before, cities_now):
        msg = 'The city {cityName} of {player} disappeared' + __island_info
        sendToBot(session, msg.format(**cities_before[disappeared_id]))

    # someone colonised
    for colonized_id in __search_additional_keys(cities_now, cities_before):
        msg = 'Player {player} created a new city {cityName}' + __island_info
        sendToBot(session, msg.format(**cities_now[colonized_id]))

    if check_fights:
        for city_id, city_before in cities_before.items():
            city_now = cities_now.get(city_id, None)
            if city_now is None:
                continue

            _before_army_action = (city_before.get('infos', {})).get('armyAction', None)
            _now_army_action = (city_now.get('infos', {})).get('armyAction', None)

            if _before_army_action is None and _now_army_action == 'fight':
                _fight_status = 'started'
            elif _before_army_action == 'fight' and _now_army_action is None:
                _fight_status = 'stopped'
            else:
                continue

            msg = ('A fight {fightStatus} in the city {cityName} '
                   'of the player {player}') + __island_info
            sendToBot(session, msg.format(fightStatus=_fight_status, **city_now))

def __search_additional_keys(source, target):
    '''
    Search for keys that were in source but are not in the target dictionary
    :param source: dict[dict]
    :param target: dict[dict]
    :return: list[int] ids of the additional keys in the source
    '''
    return [k for k in source.keys() if k not in target]
