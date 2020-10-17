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

	units = {}
	for i in range(len(unit_id_names)):
		amount = int(unit_amounts[i].replace(',', ''))
		unit_id = unit_id_names[i][0][1:]
		unit_name = unit_id_names[i][1]
		units[unit_id] = {}
		units[unit_id]['name'] = unit_name
		units[unit_id]['amount'] = amount

	return units

def plan_attack(session, city, babarians_info):
	total_units = get_units(session, city)

	if sum( [ total_units[unit_id]['amount'] for unit_id in total_units ] ) == 0:
		print('You don\'t have any troops in this city!')
		enter()
		return None

	plan = []
	while True:

		banner()

		units_available = {}
		for unit_id in total_units:

			already_sent = sum( [ p['units'][u] for p in plan for u in p['units'] if u == unit_id ] )
			if already_sent < total_units[unit_id]['amount']:
				units_available[unit_id] = {}
				units_available[unit_id]['amount'] = total_units[unit_id]['amount'] - already_sent
				units_available[unit_id]['name']   = total_units[unit_id]['name']

		if len(units_available) == 0:
			print(_('No more troops available to send'))
			enter()
			break

		attack_round = {}
		attack_round['units'] = {}
		print(_('Which troops do you want to send?').format(len(plan)+1))
		for unit_id in units_available:
			unit_amount = units_available[unit_id]['amount']
			unit_name   = units_available[unit_id]['name']
			amount_to_send = read(msg='{} (max: {}): '.format(unit_name, addDot(unit_amount)), max=unit_amount, default=0)
			if amount_to_send > 0:
				attack_round['units'][unit_id] = amount_to_send
		print('')

		if len(plan) > 0:
			round_def = len(plan) + 1
			attack_round['round'] = read(msg=_('In which battle round do you want to send them? (min: 2, default: {:d}): ').format(round_def), min=2, default=round_def)
		else:
			attack_round['round'] = 1
		print('')

		max_ships = babarians_info['ships']
		attack_round['ships'] = read(msg=_('How many ships do you want to send in this round? (min: 0, max: {:d}): ').format(max_ships), min=0, max=max_ships)
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

		plan = plan_attack(session, city, babarians_info)
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

def get_unit_weight(session, city_id, unit_id):
	params_w = {
		'view': 'unitdescription',
		'unitId': unit_id,
		'helpId': 9,
		'subHelpId': 0,
		'backgroundView': 'city',
		'currentCityId': city_id,
		'templateView': 'unitdescription',
		'actionRequest': actionRequest,
		'ajax': 1
	}
	resp = session.post(params=params_w)
	resp = json.loads(resp, strict=False)
	html = resp[1][1][1]

	weight = re.search(r'<li class="weight fifthpos" title=".*?"><span\s*class="accesshint">\'.*?\': </span>(\d+)</li>', html).group(1)
	weight = int(weight)

	return weight

def city_is_in_island(city, island):
	return city['id'] in [ c['id'] for c in island['cities'] ]

def do_it(session, island, city, babarians_info, plan, iterations):

	for round_number in range(1, iterations + 1):

		current_round_groups = [ r for r in plan if r['round'] == round_number ]
		for current_round_group in current_round_groups:

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

			ships_needed = 0
			current_units = get_units(session, city)
			for unit_id in current_round_group['units']:
				amount_to_send = min(current_round_group['units'][unit_id], current_units[unit_id]['amount'])
				attack_data['cargo_army_{}'.format(unit_id)] = amount_to_send

				if city_is_in_island(city, island) is False:
					weight = get_unit_weight(session, city['id'], unit_id)
					ships_needed += Decimal(amount_to_send * weight) / Decimal(500)

			ships_needed = math.ceil(ships_needed)

			ships_available = 0
			while ships_available < ships_needed:
				ships_available = waitForArrival(session)
			ships_available -= ships_needed

			attack_data['transporter'] = min(current_round_group['ships'], ships_available)

			session.post(payloadPost=attack_data)
