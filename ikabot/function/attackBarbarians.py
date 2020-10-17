#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import math
import gettext
import traceback
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.getJson import getCity
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.planRoutes import waitForArrival

t = gettext.translation('attackBarbarians',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

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
	level = int(level)
	gold  = resp[2][1]['js_islandBarbarianResourcegold']['text']
	gold  = int(gold)

	resources = [0] * len(materials_names)
	for i in range(len(materials_names)):
		if i == 0:
			resources[i] = int(resp[2][1]['js_islandBarbarianResourceresource']['text'])
		else:
			resources[i] = int(resp[2][1]['js_islandBarbarianResourcetradegood{:d}'.format(i)]['text'])

	html = resp[1][1][1]
	troops = re.findall(r'<div class="army \w*?">\s*<div class=".*?">(.*?)</div>\s*</div>\s*</td>\s*</tr>\s*<tr>\s*<td class="center">\s*(\d+)', html)

	total_cargo = gold + sum(resources)
	ships = math.ceil(Decimal(total_cargo) / Decimal(500))

	info = {
		'level': level,
		'gold': gold,
		'resources': resources,
		'troops': troops,
		'ships': ships
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
			units.append([unit_id_names[i][0][1:], unit_id_names[i][1], amount])

	return units

def plan_attack(session, city):
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
			already_sent = sum( [ p['units'][u] for p in plan for u in p['units'] if u == unit_id ] )
			if already_sent < unit_amount:
				units_available.append([unit_id, unit_name, unit_amount - already_sent])

		if len(units_available) == 0:
			break

		attack_round = {}
		attack_round['units'] = {}
		print(_('Which troops do you want to send?').format(len(plan)+1))
		for unit_id, unit_name, unit_amount in units_available:

			amount_to_send = read(msg='{} (max: {}): '.format(unit_name, addDot(unit_amount)), max=unit_amount, default=0)
			if amount_to_send > 0:
				attack_round['units'][unit_id] = amount_to_send
		print('')

		if len(plan) > 0:
			round_def = len(plan) + 1
			attack_round['round'] = read(msg=_('In which battle round do you want to send them? (default: {:d}): ').format(round_def), default=round_def)
		else:
			attack_round['round'] = 1
		print('')

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

		babarians_info = get_babarians_info(session, island)

		banner()
		print(_('The barbarians have:'))
		for name, amount in babarians_info['troops']:
			print(_('{} units of {}').format(amount, name))
		print('')

		banner()
		print(_('From which city do you want to attack?'))
		city = chooseCity(session)

		plan = plan_attack(session, city)
		if plan is None:
			event.set()
			return

		banner()
		print(_('How many times do you wan\'t to attack?'))
		iterations = read(min=0)
		if iterations == 0:
			event.set()
			return

		banner()
		print(_('The barbarians in [{}:{}] will be attacked {:d} times.').format(island['x'], island['y'], iterations))
		enter()

	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI attack the barbarians in [{}:{}] {:d} times\n').format(island['x'], island['y'], iterations)
	setInfoSignal(session, info)
	try:
		do_it(session, island, city, babarians_info, plan, iterations)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def do_it(session, island, city, babarians_info, plan, iterations):

	for round_number in range(1, iterations + 1):

		attack_data = {
			'action': 'transportOperations',
			'function': 'attackBarbarianVillage',
			'actionRequest': actionRequest,
			'islandId': island['id'],
			'destinationCityId': 0,
			'cargo_army_304_upkeep': 3,
			'cargo_army_304': 0,
			'cargo_army_315_upkeep': 1,
			'cargo_army_315': 0,
			'cargo_army_302_upkeep': 4,
			'cargo_army_302': 0,
			'cargo_army_303_upkeep': 3,
			'cargo_army_303': 0,
			'cargo_army_312_upkeep': 15,
			'cargo_army_312': 0,
			'cargo_army_309_upkeep': 45,
			'cargo_army_309': 0,
			'cargo_army_307_upkeep': 15,
			'cargo_army_307': 0,
			'cargo_army_306_upkeep': 25,
			'cargo_army_306': 0,
			'cargo_army_305_upkeep': 30,
			'cargo_army_305': 0,
			'cargo_army_311_upkeep': 20,
			'cargo_army_311': 0,
			'cargo_army_310_upkeep': 10,
			'cargo_army_310': 0,
			'transporter': 0,
			'barbarianVillage': 1,
			'backgroundView': 'island',
			'currentIslandId': island['id'],
			'templateView': 'plunder',
			'ajax': 1
		}

		troops_to_send = {}
		rounds = [ r for r in plan if r['round'] == round_number ]
		for attack_round in rounds:
			for unit_id in attack_round['units']:
				attack_data['cargo_army_{}'.format(unit_id)] += attack_round['units'][unit_id]
				if unit_id not in troops_to_send:
					troops_to_send[unit_id] = attack_round['units'][unit_id]
				else:
					troops_to_send[unit_id] += attack_round['units'][unit_id]

		# only send ships on the last round
		if round_number == iterations:
			ships_needed = 0
			ships_available = waitForArrival(session)
			if city['id'] not in [ city['id'] for city in island['cities'] ]:
				for unit_id in troops_to_send:

					params_w = {
						'view': 'unitdescription',
						'unitId': unit_id,
						'helpId': 9,
						'subHelpId': 0,
						'backgroundView': 'city',
						'currentCityId': city['id'],
						'templateView': 'unitdescription',
						'actionRequest': actionRequest,
						'ajax': 1
					}
					resp = session.post(params=params_w)
					resp = json.loads(resp, strict=False)
					html = resp[1][1][1]

					weight = re.search(r'<li class="weight fifthpos" title=".*?"><span\s*class="accesshint">\'.*?\': </span>(\d+)</li>', html).group(1)
					weight = int(weight)
					ships_needed += Decimal(troops_to_send[unit_id] * weight) / Decimal(500)

				ships_needed = math.ceil(ships_needed)

				ships_available = 0
				while ships_available < ships_needed:
					ships_available = waitForArrival(session)

			ships_available -= ships_needed
			transporter = min(babarians_info['ships'], ships_available)
			attack_data['transporter'] = transporter

		session.post(data=attack_data)
