#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
import sys
import threading
import json
import gzip
import re
import os
import ast
import ikabot.config as config
from pathlib import Path
from datetime import datetime
from ikabot.config import *
from ikabot.helpers.gui import enter, banner, bcolors
from ikabot.helpers.varios import wait
from ikabot.helpers.botComm import sendToBot
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getIsland
from ikabot.helpers.process import set_child_mode

t = gettext.translation('dumpWorld', localedir, languages=languages, fallback=True)
_ = t.gettext

LINE_UP = '\033[1A'
LINE_CLEAR = '\x1b[2K'
stop_updating = threading.Event()
lock = threading.Lock()
#              status, history, start_time
shared_data = ['','',0,stop_updating, lock]
home = 'USERPROFILE' if isWindows else 'HOME'
selected_islands = set()


def dumpWorld(session, event, stdin_fd, predetermined_input):
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
        banner()
        if os.path.exists(os.getenv(home) + '/ikabot_world_dumps'):
            print('1) Create new dump')
            print('2) Load existing dump')
            choice = read(min=1, max=2, digit=True)
            if choice == 2:
                return view_dump(session, event)
        banner()
        print('{}⚠️ BEWARE - THE RESULTING DUMP CONTAINS ACCOUNT IDENTIFYING INFORMATION ⚠️{}\n'.format(bcolors.WARNING, bcolors.ENDC))
        print('This action will take a couple of hours to complete. Are you sure you want to initiate a data dump now? (Y|N)')
        choice = read(values=['y', 'Y', 'n', 'N'])
        if (choice in ['n','N']):
            event.set()
            return
        print('Type in the waiting time between each request in miliseconds (default = 1500): ')
        choice = read(min=0, max=10000, digit=True, default=1500)
        waiting_time = int(choice)/1000
        print('Start scan form island id (0 to start from beginning) (default = 0): ')
        choice = read(min=0, digit=True, default=0)
        start_id = int(choice)
        print('Do you want only shallow data about the islands? If yes you will not be able to search the dump by player names but the dump will be quick. (Y|N): ')
        choice = read(values=['y', 'Y', 'n', 'N'])
        shallow = choice
        
        thread = threading.Thread(target=update_terminal, args=(shared_data,))
        thread.start()
        set_child_mode(session)
        info = _('\nDumped world data\n')
        setInfoSignal(session, info)

        dump_path = do_it(session, waiting_time, start_id, shallow)

        shared_data[3].set()
        shared_data[4].acquire()
        time.sleep(5)

        banner()
        print('\n{}SUCCESS!{} World data has been dumped to {} in {}s \n'.format(bcolors.GREEN, bcolors.ENDC,dump_path, str(round(time.time()-shared_data[2]))))
        enter()
        event.set()
        return
    except Exception:
        shared_data[3].set()
        shared_data[4].acquire(timeout=10)
        event.set()
        msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
        sendToBot(session, msg)
        return


def do_it(session, waiting_time, start_id, shallow):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    waiting_time : int
        Time to wait between each network request (to prevent getting rate limited)
    start_id : int
        Id of the island to start the dump from (0 starts from beginning)
    shallow : str
        String that determines if the data should be shallow (only map accessible data)
    
    Returns
    -------
    dump_path: str
    """

    shared_data[2] = time.time()
    world = {'name': 's' + str(session.mundo) + '-' + str(session.servidor),
             'self_name': session.username,
             'dump_start_date': time.time(),
             'dump_end_date': 0,
             'islands': [],
             'shallow': shallow in ['y', 'Y']
            }
    shared_data.append(world)
    #scan 0 to 50 x and y
    shallow_islands = []
    update_status('Initiating first map sweep', 0, 0, True)
    update_status('Getting (0-50,0-50) islands', 25, 1.25)
    data = session.post('action=WorldMap&function=getJSONArea&x_min=0&x_max=50&y_min=0&y_max=50')
    for x, val in json.loads(data)['data'].items():
        for y, val2 in val.items():
            shallow_islands.append({'x': x, 'y': y, 'id': val2[0], 'name': val2[1], 'resource_type': val2[2], 'miracle_type': val2[3], 'wood_lvl': val2[6], 'players': val2[7] })
    update_status('Getting (50-100,0-50) islands', 50, 2.5)
    time.sleep(0.5)
    data = session.post('action=WorldMap&function=getJSONArea&x_min=50&x_max=100&y_min=0&y_max=50')
    for x, val in json.loads(data)['data'].items():
        for y, val2 in val.items():
            shallow_islands.append({'x': x, 'y': y, 'id': val2[0], 'name': val2[1], 'resource_type': val2[2], 'miracle_type': val2[3], 'wood_lvl': val2[6], 'players': val2[7] })
    update_status('Getting (0-50,50-100) islands', 75, 3.75)
    time.sleep(0.5)
    data = session.post('action=WorldMap&function=getJSONArea&x_min=0&x_max=50&y_min=50&y_max=100')
    for x, val in json.loads(data)['data'].items():
        for y, val2 in val.items():
            shallow_islands.append({'x': x, 'y': y, 'id': val2[0], 'name': val2[1], 'resource_type': val2[2], 'miracle_type': val2[3], 'wood_lvl': val2[6], 'players': val2[7] })
    update_status('Getting (50-100,50-100) islands', 100, 5)
    time.sleep(0.5)
    data = session.post('action=WorldMap&function=getJSONArea&x_min=50&x_max=100&y_min=50&y_max=100')
    for x, val in json.loads(data)['data'].items():
        for y, val2 in val.items():
            shallow_islands.append({'x': x, 'y': y, 'id': val2[0], 'name': val2[1], 'resource_type': val2[2], 'miracle_type': val2[3], 'wood_lvl': val2[6], 'players': val2[7] })

# [
# "58",         //id 0
# "Phytios",    //name 1
# "1",          //resource type 2
# "2",          //type of miracle 3
# "5",          // ?? 4
# "4",          // ?? 5
# "9",          // lumber level  6
# "12",         // number of people 7
# 0,            // piracy in range 8
# "0",          // helios tower 9
# "0",          // red 10
# "0"           // blue 11
# ]
    
    dump_path = os.getenv(home) + '/ikabot_world_dumps/s' + str(session.mundo) + '-' + str(session.servidor) + '/'
    dump_path = dump_path.replace('\\','/')
    dump_name = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H-%M-%S') + '.json.gz'

    if shallow in ['y','Y']:
        dump_name = dump_name.replace('.json.gz', '_shallow') + '.json.gz'
        update_status('Shallow dump is on. Dumping data...', 100, 100, True)
        world['islands'] = shallow_islands
        dump(world, dump_path, dump_name)
        return dump_path + dump_name

    all_island_ids = set()
    total_settlements = 0
    for island in shallow_islands:
        all_island_ids.add(island['id'])
        total_settlements += int(island['players'])

    update_status('Got {} islands with {} towns in total'.format(len(all_island_ids), str(total_settlements)), 100, 5, True)
    update_status('Getting data for each island. This will take a while...', 0, 5, True)

    #scan each island

    world_islands_number = len(all_island_ids)
    all_island_ids = list(split(sorted(map(int, all_island_ids)), 1))
    
    dump_islands(shared_data, all_island_ids[0], waiting_time, start_id, session, world_islands_number)

    update_status('Got {} individual islands'.format(world_islands_number), 100, 100, True)

    update_status('Dumping data to {}'.format(dump_path + dump_name), 100, 100, True)

    dump(shared_data[5], dump_path, dump_name)
    

    return dump_path + dump_name

def split(a, n):
    k, m = divmod(len(a), n)
    return (a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n))

def dump(world, dump_path, dump_name):
    world['dump_end_date'] = time.time()
    p = Path(dump_path)
    p.mkdir(exist_ok=True, parents=True)
    with gzip.open(dump_path+dump_name,'wb') as file:
        json_string = json.dumps(world).encode('utf-8')
        file.write(json_string)
       
def dump_islands(shared_data, all_island_ids, waiting_time, start_id, session, world_islands_number):
    for i, island_id in enumerate(sorted(map(int, all_island_ids))):
        if(int(island_id) < start_id):
            continue
        update_status('Getting island id {}'.format(island_id), len(shared_data[5]['islands'])/world_islands_number*100, 5+(len(shared_data[5]['islands'])/world_islands_number * 95))
        html = ''
        try:
            html = session.get('view=island&islandId=' + str(island_id))
        except Exception:
            # try again
            html = session.get('view=island&islandId=' + str(island_id))
        island = getIsland(html)
        shared_data[4].acquire()
        shared_data[5]['islands'].append(island)
        shared_data[4].release()
        time.sleep(waiting_time)

def update_terminal(shared_data):
    while(True):
        banner()
        print('\n')
        shared_data[4].acquire()
        print(shared_data[1])
        shared_data[4].release()
        chars = ['\\','|','/','─']
        for i in range(20):
            shared_data[4].acquire()
            print(' '*120, end='\r')
            print(shared_data[0] + ',\tdt: ' + str(round(time.time()-shared_data[2],2)) + 's\t' + chars[i%4] , end='\r')
            shared_data[4].release()
            time.sleep(0.05)
        if stop_updating.is_set():
            return
        
def update_status(message, percent, percent_total, add_history = False):
    shared_data[4].acquire()
    shared_data[0] = message + '\t' + str(round(percent,1)) + '%,\ttotal: ' + str(round(percent_total,1)) + '%'
    if(add_history):
        shared_data[1] += shared_data[0] + '\n'
    shared_data[4].release()
    

def view_dump(session, event):
    files = [file.replace('\\','/') for file in get_files(os.getenv(home) + '/ikabot_world_dumps') if '.json.gz' in file ]

    print('All dumps are stored in ' + os.getenv(home) + '/ikabot_world_dumps\n')
    print('Choose a dump to view:')
    for i, file in enumerate(files):
        print(str(i) + ') ' + file.split('/')[-2] + ' ' + file.split('/')[-1].replace('.json.gz','').replace('_',' '))
    choice = read(min = 0, max = len(files)-1, digit=True)
    print('Loading dump...')
    selected_dump = files[choice]
    with gzip.open(selected_dump, 'rb') as file:
        selected_dump = json.load(file)
    
    while True:
        banner()
        print_map(selected_dump['islands'])
        print('0) Back')
        print('1) Search islands by island criteria')
        if not selected_dump['shallow']:
            print('2) Search islands by player name')
            print('3) Search for nearest inactive players')

        choice = read(min=0, max=3, digit=True)
        if choice == 0:
            event.set()
            return
        elif choice == 1:
            print('Search island by a certain criteria. The available properties of an island are:')
            print('resource_type : [1,2,3,4] // these are  Wine, Marble, Cristal, Sulfur')
            print('miracle_type : [1,2,3,4,5,6,7,8] // hephaistos forge is number 5')
            print('wood_lvl : [1..] // this is the forest level on the island')
            print('players : [0..] // number of players on the island')
            print('ex. If I wanted to find all islands with less than 10 players and forest level 30 with hephaistos I would type in:')
            print('players < 10 and wood_lvl == 30 and miracle_type == 5\n')
            condition = read(msg="Enter the condition: ")

            try:
                filtered_islands = [island for island in filter(lambda x: filter_on_condition(x, condition), selected_dump['islands'] if selected_dump['shallow'] else convert_to_shallow(selected_dump['islands']))]
            except (SyntaxError, KeyError):
                print('Condition is bad, please use only the available island properties and use python standard conditional sytnax (and, or, <, >, ==, (, ), etc... )')
                enter()
                continue
            
            print('The satisfying islands are:')
            [print(island) for island in filtered_islands]
            enter()
        elif choice == 2:
            if selected_dump['shallow']:
                print('You can not search by player name because this dump is shallow and doesn\'t contain data about players!')
                enter()
                continue
            player_name = read(msg='Type in the player name: ')
            # search for players by name
            players = []
            for island in selected_dump['islands']:
                for city in island['cities']:
                    if city['type'] != 'empty' and player_name in city['Name']:
                        players.append((player_name, island['id']))
            # return if none are found
            if not len(players):
                print('No players found!')
                enter()
                continue
            # select one 
            print('Chose a player to add to selection: ')
            for i, player in enumerate(unique_tuples(players)):
                print(str(i) + ') ' + player[0])
            choice = read(min=0, max=len(list(unique_tuples(players)))-1, digit=True)
            # add his islands to selection
            for player in players:
                if player[0] == list(unique_tuples(players))[choice][0]:
                    selected_islands.add(int(player[1]))
        elif choice == 3:
            if selected_dump['shallow']:
                print('You can not search by player name because this dump is shallow and doesn\'t contain data about players!')
                enter()
                continue
            coords = read(msg='Type in a center point (x,y): ').replace('(','').replace(')','').split(',')
            coords = (int(coords[0]), int(coords[1]))
            number_of_inactives = read(msg='How many inactives should be displayed? (min=1, default=25): ', min = 1, digit=True, default=25)
            #sort islands based on distance from center point
            islands_sorted = sorted(selected_dump['islands'], key=lambda island: ((island['x'] - coords[0]) ** 2 + (island['y'] - coords[1]) ** 2) ** 0.5)
            print('The nearest 25 inactive players are: ')
            #below follows the unholiest way to get the first n cities which are contained in an island object which is contained in a list of islands without duplicates in one line of code using python list comprehension
            seen = set()
            inactives = [city for island in islands_sorted for city in island['cities'] if city['type'] != 'empty' and city['state'] == 'inactive' and isinstance([(seen.add(city['Name']),) if city['Name'] not in seen else None][0],tuple)][:number_of_inactives]
            for i, city in enumerate(inactives):
                print(str(i+1) + ') ' + city['Name'])
            enter()


def print_map(islands):
    """Prints out a 100x100 matrix with all world islands on it. Selected islands are colored red.
    Parameters
    ----------
    islands : [object]
        List of island objects to be displayed
    """

    map = [[bcolors.DARK_BLUE + '██' + bcolors.ENDC for j in range(100)] for i in range(100)] # 100x100 matrix of dark blue ██
    selected_island_coords = []

    for island in islands:
        if int(island['id']) in selected_islands:
            map[int(island['x'])-1][int(island['y'])-1] = bcolors.DARK_RED + '◉ ' + bcolors.ENDC 
            selected_island_coords.append((int(island['x']),int(island['y'])))
        else:
            map[int(island['x'])-1][int(island['y'])-1] = bcolors.DARK_GREEN + '◉ ' + bcolors.ENDC

    for row in reversed(map):
        print(''.join(row))

    print(bcolors.DARK_BLUE + '██' + bcolors.ENDC + ' - Water, ' + \
          bcolors.DARK_GREEN + '◉' + bcolors.ENDC + ' - Island, '+ \
          bcolors.DARK_RED + '◉' + bcolors.ENDC + ' - Selected\n'
        )

    print('Selected islands: ' + str(selected_island_coords))
    

def filter_on_condition(island, condition):
    """Returns true if island satisfies condition
    Parameters
    ----------
    island : object
        Island to be tested on condition
    condition : str
        String that represents a valid python condition to be applied to filter the list of islands

    Returns
    -------
    is_satisfied : bool
        Bool indicating whether or not the island object satisfies the condition
    """

    condition = ast.parse(condition)
    for node in ast.walk(condition):
        if isinstance(node, ast.Compare):
            left = node.left.id
            right = node.comparators[0].n if isinstance(node.comparators[0], ast.Num) else node.comparators[0].id
            op = node.ops[0]
            if op.__class__ == ast.Lt:
                if not int(island[left]) < int(right):
                    return False
            elif op.__class__ == ast.Gt:
                if not int(island[left]) > int(right):
                    return False
            elif op.__class__ == ast.Eq:
                if not int(island[left]) == int(right):
                    return False
    return True

    

def convert_to_shallow(islands):
    """Converts a list of islands from a deep dump into a shallow dump version of that list
    Parameters
    ----------
    islands : [object]
        List of island objects to be converted
    
    Returns
    -------
    islands : [object]
        List of objects that represent the stripped-down version of an island 
    """
    return [{'x': str(island['x']), 'y': str(island['y']), 'id': island['id'], 'name': island['name'], 'resource_type': island['tradegood'], 'miracle_type': island['wonder'], 'wood_lvl': island['resourceLevel'], 'players': len([city for city in island['cities'] if city['type'] != 'empty'])} for island in islands]

def unique_tuples(tuples):
    """Iterates over tuples with a unique first element
    """
    seen = {}
    for t in tuples:
        if t[0] not in seen:
            seen[t[0]] = True
            yield t

def get_files(path):
    """
    Returns all full paths to every file in a directory and all it's subdirectories
    Parameters
    ----------
    path : str
        Path to directory
    Returns
    -------
    files : list
    """
    files = []
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            files.append(os.path.join(dirpath, filename))
    return files
