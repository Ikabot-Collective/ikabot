#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from cgi import print_arguments
from email.headerregistry import ContentTransferEncodingHeader
import os
import math
from re import X
import datetime
import time
import gettext
import traceback
import sys
import ikabot.config as config
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter, enter
from ikabot.helpers.varios import wait
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getIsland
from ikabot.helpers.process import set_child_mode
from tinydb import TinyDB, Query, where

#Emojis
e_scanning = u'\U0001F4E1'
e_error = u'\U0001F6A8'
e_ok = u'\U00002705'
e_sad = u'\U0001F612'
e_this = u'\U0001F449'
e_clock = u'\U0000231B'
e_monkey = u'\U0001F648'
e_this_down = u'\U0001F447'

t = gettext.translation('searchInactive', localedir, languages=languages, fallback=True)
_ = t.gettext

home = 'USERPROFILE' if isWindows else 'HOME'

def searchInactive(session, event, stdin_fd, predetermined_input):
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    
    try:
        banner()
        print('Find inactive players')
        print('(0) Exit')
        print('(1) Start scan process...')
        choice = read(min=0, max=1)
        
        if choice == 0:
            event.set()
            return
        elif choice == 1:

            my_coords = []

            def sqr(x):
                return x*x
            
            banner()
            print('Insert your reference coordinates, example: 50:50')
            coords_string = read()
            # Get Reference Coordinates
            x_reference = int(coords_string.split(':')[0])
            y_reference = int(coords_string.split(':')[1])
            
            banner()
            print("How far away from your reference coordinates in hours not considering Wonder (minimum is 1h)?")
            distance_hours = read(min=1, digit=True)
            distance_treshoold = distance_hours * 3600

            for x in range(x_reference - (distance_hours * 3), x_reference + (distance_hours * 3)):
                for y in range(y_reference - (distance_hours * 3), y_reference + (distance_hours * 3)):
                    
                    travel_seconds = math.sqrt(abs(sqr((x_reference - x) * 20 * 60) + sqr((y_reference - y) * 20 * 60)))

                    if (travel_seconds <= distance_treshoold):
                        my_coords.append({"coords": f"{x}:{y}", "seconds": travel_seconds})
        else:
            pass

        banner()
        print('How frequently should I scan for inactive players (minimum is 60m)?')
        _time = read(min=60, digit=True)

        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = _(f'\n{e_scanning} {e_scanning} {e_scanning} {e_scanning} {e_scanning}\n\nProcess: Inactive Players Scanner\nScanning to {distance_hours} hours distance from [{x_reference}:{y_reference}]\nWait time: {_time} minutes\n\n {e_this_down} {e_this_down} {e_this_down} {e_this_down} {e_this_down}\n\n')

    setInfoSignal(session, info)
    
    try:
        sendToBot(session, info)
        do_it(session, my_coords, _time)
    except Exception as e:
        msg = _(f'\n{e_error} {e_error} {e_error} {e_error} {e_error}\n\nError in:\n{info}\nCause:\n{traceback.format_exc()}')
        sendToBot(session, msg)
    finally:
        session.logout()

def do_it(session, coords, _time):
    while True:
        news = []
        db = TinyDB(f"{os.getenv(home)}/inactive_players_{str(session.username)}_{str(session.servidor)}.json")
        #Sort list by seconds, meaning, nearest target should go first..
        sorted_coordenates = sorted(coords, key=lambda d: d['seconds'], reverse=False)
        for coord in sorted_coordenates:
            coords_before_manipulation = coord['coords']
            my_coords = coord['coords']
            elapse_time = float(coord['seconds'])
            my_coords = '&xcoord=' + my_coords
            my_coords = my_coords.replace(':', '&ycoord=')
            html = session.get('view=island' + my_coords)
            island = getIsland(html)

            for city in island["cities"]:
                if (coords_before_manipulation == f"{island['x']}:{island['y']}" and city['id'] > 0 and int(city['level']) > 10):
                    
                    player_str_template = f"{e_this} {city['Name']} - {city['name']} ({city['level']}), [{island['x']}:{island['y']}] - " + time.strftime('%H:%M:%S', time.gmtime(elapse_time))

                    db_city = db.search(where("id") == city['id'])
                    if (len(db_city)) == 0:

                        # Inactive, city hall > 10
                        db.insert({'id': city['id'], 'state': city['state'], 'x': island['x'], 'y': island['y'], 'last_update': datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")})
                        if(city['state'] == 'inactive'):
                            news.append(player_str_template + "  (NEW)")
                    else:
                        c = db_city[0]
                        if(city['state'] != c['state']):
                            if (city['state'] == '' or city['state'] == 'vacation'):
                                # Exists on DB, status either active or vacations, delete row since we don't care about these active players
                                db.remove(where('id') == c['id'])
                            if (city['state'] == 'inactive'):
                                db.update({'state': city['state'], 'x': island['x'], 'y': island['y'], 'last_update': datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")}, Query().id == c['id'])
                                #  Exists on DB, status from active or vacations to inactive, update it on DB
                                news.append(player_str_template + "  (EXISTING)")

        complement = ""
    
        if(len(news) > 0):
            complement = f"\n{e_clock} Time not calculated based on WONDER {e_monkey}\n\n" + "\n".join(news)
        else:
            complement = f"\nNo new victims found {e_sad}!"

        #Send message to telegram, if message lenght is > 3800 char the the message is splitted in groups
        msg_lenght = 3800
        if(len(complement) > msg_lenght):
            msg_array = [complement[i:i+msg_lenght] for i in range(0, len(complement), msg_lenght)]
            for msg in msg_array:
                sendToBot(session, f'{e_ok} Process running at {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")}\n{msg}')
        else:
            sendToBot(session, f'{e_ok} Process running at {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")}\n{complement}')

        wait(_time * 60)