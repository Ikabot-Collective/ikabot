#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.getJson import getCity
from ikabot.helpers.signals import setInfoSignal

t = gettext.translation('attackBarbarians',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def choose_island(session):
	idsIslands = getIslandsIds(session)
	islands = []
	for idIsland in idsIslands:
		html = session.get(island_url + idIsland)
		island = getIsland(html)
		if island['barbarians']['destroyed'] == 0:
			islands.append(island)

	if len(islands) == 0:
		print(_('No islands available!'))
		enter()
		return None

	if len(islands) == 1:
		return islands[0]

	islands.sort(key=lambda island:island['id'])

	longest_island_name_length = 0
	for island in islands:
		longest_island_name_length = max(len(island['name']), longest_island_name_length)

	pad = lambda island_name: ' ' * (longest_island_name_length - len(island_name)) + island_name

	print(_('In which island do you want to attack the barbarians?'))
	print(_(' 0) Exit'))
	for i, island in enumerate(islands):
		num = ' ' + str(i+1) if i < 9 else str(i+1)
		print(_('{}) [{}:{}] {} ({}) : barbarians lv: {} ({})').format(num, island['x'], island['y'], pad(island['name']), materials_names[int(island['tradegood'])][0].upper(), island['barbarians']['level'], island['barbarians']['city']))

	index = read(min=0, max=len(islands))
	if index == 0:
		return None
	else:
		return islands[index-1]

def get_babarians_info(session, island):
	params = {"view": "barbarianVillage", "destinationIslandId": island['id'], "oldBackgroundView": "city", "cityWorldviewScale": "1", "islandId": island['id'], "backgroundView": "island", "currentIslandId": island['id'], "actionRequest": actionRequest, "ajax": "1"}
	resp = session.post(params=params)
	resp = json.loads(resp, strict=False)

	level = resp[2][1]['js_islandBarbarianLevel']['text']
	gold  = resp[2][1]['js_islandBarbarianResourcegold']['text']

	resources = [0] * len(materials_names)
	for i in range(len(materials_names)):
		if i == 0:
			resources[i] = resp[2][1]['js_islandBarbarianResourceresource']['text']
		else:
			resources[i] = resp[2][1]['js_islandBarbarianResourcetradegood{:d}'.format(i)]['text']

	html = resp[1][1][1]
	troops = re.findall(r'<div class="army \w*?">\s*<div class=".*?">(.*?)</div>\s*</div>\s*</td>\s*</tr>\s*<tr>\s*<td class="center">\s*(\d+)', html)

	info = {
		'level': level,
		'gold': gold,
		'resources': resources,
		'troops': troops
	}

	return info

def get_city_in_island(session, island):
	cities = [ city for city in island['cities'] if city['type'] != 'empty' and city['Name'] == session.username ]
	if len(cities) == 1:
		return cities[0]

	cities.sort(key=lambda city:city['id'])

	longest_city_name_length = 0
	for city in cities:
		longest_city_name_length = max(len(city['name']), longest_city_name_length)

	pad = lambda city_name: ' ' * (longest_city_name_length - len(city_name)) + city_name

	print('With which city do you want to attack?')
	print(' 0) {}'.format(pad('Exit')))
	for i, city in enumerate(cities):
		num = ' ' + str(i+1) if i < 10 else str(i+1)
		print('{}) {}'.format(num, pad(city['name'])))
	index = read(min=0, max=len(cities))
	if index == 0:
		return None
	else:
		return cities[index-1]

def attackBarbarians(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	try:
		banner()

		island = choose_island(session)
		if island is None:
			event.set()
			return

		info = get_babarians_info(session, island)

		print(_('The barbarians have:'))
		for name, amount in info['troops']:
			print(_('{} units of {}').format(amount, name))
		print('')

		city = get_city_in_island(session, island)
		if city is None:
			event.set()
			return

	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI attack the barbarians in [{}:{}] {:d} times\n').format(island['x'], island['y'], iterations)
	setInfoSignal(session, info)
	try:
		do_it(session, island, iterations)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def do_it(session, island, iterations):
	pass
