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

def get_units(session, city):
	params = {
		'view': 'cityMilitary',
		'activeTab': 'tabUnits',
		'cityId': city['id'],
		'backgroundView': 'city',
		'currentCityId': city['id'],
		'currentTab': 'multiTab1',
		'actionRequest': actionRequest,
		'ajax': '1'
	}

	resp = session.post(params=params)
	resp = json.loads(resp, strict=False)
	html = resp[1][1][1]
	html = html.split('<div class="fleet')[0]

	unit_id_names   = re.findall(r'<div class="army (.*?)">\s*<div class="tooltip">(.*?)<\/div>', html)
	unit_amounts = re.findall(r'<td>([\d,]+)\s*</td>', html)

	units = []

	for i in range(len(unit_id_names)):
		amount = int(unit_amounts[i].replace(',', ''))
		if amount > 0:
			units.append([unit_id_names[i][0], unit_id_names[i][1], amount])

	return units

def plan_attack(session, city, barbarians_info):
	units = get_units(session, city)

	if len(units) == 0:
		print('You don\'t have any troops in this city!')
		enter()
		return None

	plan = []
	while True:

		banner()

		units_available = []
		for unit_id, unit_name, unit_amount in units:
			already_sent = sum( [ p[u] for p in plan for u in p if u == unit_id ] )
			if already_sent < unit_amount:
				units_available.append([unit_id, unit_name, unit_amount - already_sent])

		if len(units_available) == 0:
			break

		attack_round = {}
		print(_('Which troops do you want to send?').format(len(plan)+1))
		for unit_id, unit_name, unit_amount in units_available:

			amount_to_send = read(msg='{} (max: {}): '.format(unit_name, addDot(unit_amount)), max=unit_amount, default=0)
			if amount_to_send > 0:
				attack_round[unit_id] = amount_to_send
		print('')

		if len(plan) > 0:
			round_def = len(plan) + 1
			attack_round['round'] = read(msg=_('In which battle round do you want to send them? (default: {:d}): ').format(round_def), default=round_def)
		else:
			attack_round['round'] = 1

		plan.append(attack_round)

		print(_('Do you want to send another round of troops? [y/N]'))
		resp = read(values=['y', 'Y', 'n', 'N'], default='n')
		if resp.lower() != 'y':
			break

	return plan

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

		print('From which city do you want to attack?')
		city = chooseCity(session)

		plan = plan_attack(session, city, info)
		if plan is None:
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
