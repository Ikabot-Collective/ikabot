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

__inform_fights = 'inform-fights'
__inform_inactive = 'inform-inactive'
__inform_vacation = 'inform-vacation'
__yes_no_values = ['y', 'Y', 'n', 'N']
__state_inactive = 'inactive'
__state_vacation = 'vacation'

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

        print('How frequently should the islands be searched in minutes (minimum is 3)?')
        waiting_minutes = read(min=3, digit=True)

        print('Do you wish to be notified if on these islands')
        inform_list = []
        for val, msg in [
            [__inform_fights, 'A fight breaks out or stops'],
            [__inform_inactive, 'A player becomes active/inactive'],
            [__inform_vacation, 'A player activates/deactivates vacation'],
        ]:
            if read(
                msg=' - {}? (Y|N)'.format(msg),
                values=['y', 'Y', 'n', 'N'],
              ).lower() == 'y':
                inform_list.append(val)

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
        __execute_monitoring(session, island_ids, waiting_minutes, inform_list)
    except Exception as e:
        msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()

def __execute_monitoring(session, specified_island_ids, waiting_minutes, inform_list):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    specified_island_ids : list[dict]
        A list containing island objects which should be searched, if an empty list is passed, all the user's colonised islands are searched
    waiting_minutes : int
        The time in minutes between two consecutive searches
    inform_list : list[]
        List of notification types to send
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
                    inform_list=inform_list
                )

            # update cities_before_per_island for the current island
            cities_before_per_island[island_id] = dict(cities_now)

        session.setStatus(f'Checked islands {str([int(i) for i in islands_ids]).replace(" ","")} @ {getDateTime()[-8:]}')
        wait(waiting_minutes * 60)

def __extract_cities(island):
    """
    Extract the cities from island
    :param island: dict[]
    :return: dict[dict] cityId -> city
    """
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

def __compare_island_cities(session, cities_before, cities_now, inform_list):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    cities_before : dict[dict]
        A dict of cities on the island on the previous check
    cities_now : dict[dict]
        A dict of cities on the island on the current check
    inform_list : list[]
        List of notification types to send
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

    if __inform_inactive in inform_list:
        for city, state_before, state_now in __search_state_change(
            cities_before,
            cities_now,
            lambda c: c['state']
        ):
            if state_before == __state_inactive:
                _status = 'active again'
            elif state_now == __state_inactive:
                _status = 'inactive'
            else:
                continue

            msg = ('The player {player} with the city {cityName} '
                   'became {status}!') + __island_info
            sendToBot(session, msg.format(status=_status, **city))

    if __inform_vacation in inform_list:
        for city, state_before, state_now in __search_state_change(
            cities_before,
            cities_now,
            lambda c: c['state']
        ):
            if state_before == __state_vacation:
                _status = 'returned from'
            elif state_now == __state_vacation:
                _status = 'went on'
            else:
                continue

            msg = ('The player {player} with the city {cityName} '
                   '{status} vacation!') + __island_info
            sendToBot(session, msg.format(status=_status, **city))

    if __inform_fights in inform_list:
        for city, _before_army_action, _now_army_action in __search_state_change(
            cities_before,
            cities_now,
            lambda c: c.get('infos', {}).get('armyAction', None)
        ):

            if _now_army_action == 'fight':
                _fight_status = 'started'
            elif _before_army_action == 'fight':
                _fight_status = 'stopped'
            else:
                continue

            msg = ('A fight {fightStatus} in the city {cityName} '
                   'of the player {player}') + __island_info
            sendToBot(session, msg.format(fightStatus=_fight_status, **city))

def __search_additional_keys(source, target):
    """
    Search for keys that were in source but are not in the target dictionary
    :param source: dict[dict]
    :param target: dict[dict]
    :return: list[int] ids of the additional keys in the source
    """
    return [k for k in source.keys() if k not in target]

def __search_state_change(cities_before, cities_now, state_getter):
    """
    Searches for change in state between cities_before and cities_now with the
    state_getter function.
    Returns list of changes (city, old_state, new_state)
    !!!IMPORTANT!!! old_state != new_state
    :param cities_before: dict[dict[]]
    :param cities_now:    dict[dict[]]
    :param state_getter:  dict[] -> string
    :return: list[[city_now, old_state, new_state]]
    """
    _res = []
    for city_id, city_before in cities_before.items():
        city_now = cities_now.get(city_id, None)
        if city_now is None:
            continue

        _state_before = state_getter(city_before)
        _state_now = state_getter(city_now)
        if _state_before != _state_now:
            _res.append([city_now, _state_before, _state_now])

    return _res
