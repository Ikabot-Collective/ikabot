#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
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
from ikabot.helpers.naval import *
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
		islands.append(island)

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
		if island['barbarians']['destroyed'] == 1:
			warn = _('(currently destroyed)')
		else:
			warn = ''
		print(_('{}) [{}:{}] {} ({}) : barbarians lv: {} ({}) {}').format(num, island['x'], island['y'], pad(island['name']), materials_names[int(island['tradegood'])][0].upper(), island['barbarians']['level'], island['barbarians']['city'], warn))

	index = read(min=0, max=len(islands))
	if index == 0:
		return None
	else:
		return islands[index-1]

def get_barbarians_lv(session, island):
	params = {"view": "barbarianVillage", "destinationIslandId": island['id'], "oldBackgroundView": "city", "cityWorldviewScale": "1", "islandId": island['id'], "backgroundView": "island", "currentIslandId": island['id'], "actionRequest": actionRequest, "ajax": "1"}
	resp = session.post(params=params)
	resp = json.loads(resp, strict=False)

	level = int(resp[2][1]['js_islandBarbarianLevel']['text'])
	gold  = int(resp[2][1]['js_islandBarbarianResourcegold']['text'].replace(',', ''))

	resources = [0] * len(materials_names)
	for i in range(len(materials_names)):
		if i == 0:
			resources[i] = int(resp[2][1]['js_islandBarbarianResourceresource']['text'].replace(',', ''))
		else:
			resources[i] = int(resp[2][1]['js_islandBarbarianResourcetradegood{:d}'.format(i)]['text'].replace(',', ''))

	html = resp[1][1][1]
	troops = re.findall(r'<div class="army \w*?">\s*<div class=".*?">(.*?)</div>\s*</div>\s*</td>\s*</tr>\s*<tr>\s*<td class="center">\s*(\d+)', html)

	total_cargo = sum(resources)
	ships = math.ceil(Decimal(total_cargo) / Decimal(500))

	info = {
		'island_id': island['id'],
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
	unit_amounts = re.findall(r'<td>(.*?)\s*</td>', html) # fixed lior 

	units = {}
	for i in range(len(unit_id_names)):
		amount = int(unit_amounts[i].replace(',', '').replace('-', '0'))
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
	total_ships = None
	last = False
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
			amount_to_send = read(msg='{} (max: {}): '.format(unit_name, addThousandSeparator(unit_amount)), max=unit_amount, default=0)
			if amount_to_send > 0:
				attack_round['units'][unit_id] = amount_to_send
		print('')

		attack_round['loot'] = last
		if last:
			attack_round['round'] = len(plan) + 1
		else:
			if len(plan) > 0:
				round_def = len(plan) + 1
				attack_round['round'] = read(msg=_('In which battle round do you want to send them? (min: 2, default: {:d}): ').format(round_def), min=2, default=round_def)
			else:
				attack_round['round'] = 1
		print('')

		#max_ships = babarians_info['ships']
		if last is False:
			if total_ships is None:
				total_ships = getTotalShips(session)
			max_ships = total_ships - sum( [ ar['ships'] for ar in plan ] )
			if max_ships > 0:
				attack_round['ships'] = read(msg=_('How many ships do you want to send in this round? (min: 0, max: {:d}): ').format(max_ships), min=0, max=max_ships)
				print('')
			else:
				attack_round['ships'] = 0

		plan.append(attack_round)

		if last:
			break

		print(_('Do you want to send another round of troops? [y/N]'))
		resp = read(values=['y', 'Y', 'n', 'N'], default='n')
		if resp.lower() != 'y':
			print('')
			print(_('Do you want to select the troops that will be used to collect the remaining resources? (they need to destroy the wall) [y/N]'))
			resp = read(values=['y', 'Y', 'n', 'N'], default='n')
			if resp.lower() != 'y':
				break
			else:
				last = True


	plan.sort(key=lambda ar:ar['round'])
	return plan

def attackBarbarians(session, event, stdin_fd, predetermined_input):
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

		island = choose_island(session)
		if island is None:
			event.set()
			return

		babarians_info = get_barbarians_lv(session, island)

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
		print(_('The barbarians in [{}:{}] will be attacked.').format(island['x'], island['y']))
		enter()

	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI attack the barbarians in [{}:{}]\n').format(island['x'], island['y'])
	setInfoSignal(session, info)
	try:
		do_it(session, island, city, babarians_info, plan)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def get_unit_data(session, city_id, unit_id):
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

	speed = re.search(r'(\d+)\s*<br\/>\s*<span class="textLabel">.*?\s*:<\/span>\d+<br\/>\s*<\/div>\s*<div class="clearfloat"><\/div>\s*<div class="weapon">', html).group(1)
	speed = int(speed)

	return {'speed': speed, 'weight': weight}

def city_is_in_island(city, island):
	return city['x'] == island['x'] and city['y'] == island['y']

def get_barbarians_info(session, island_id):
	query = {
		'view': 'barbarianVillage',
		'destinationIslandId': island_id,
		'backgroundView': 'island',
		'currentIslandId': island_id,
		'actionRequest': actionRequest,
		'ajax': 1
	}
	resp = session.post(params=query)
	resp = json.loads(resp, strict=False)
	return resp

def wait_until_can_attack(session, city, island, travel_time=0):
	html = session.get(island_url + island['id'])
	island = getIsland(html)

	if island['barbarians']['underAttack'] == 0 and island['barbarians']['destroyed'] == 0:
		# an attack might be on its way
		wait_for_arrival(session, city, island)
		html = session.get(island_url + island['id'])
		island = getIsland(html)

	if island['barbarians']['underAttack'] == 1:
		# a battle is taking place
		attacks = get_current_attacks(session, city['id'], island['id'])
		attacks_fighting = filter_fighting(attacks)
		eventTimes = [ attack['eventTime'] for attack in attacks_fighting ]
		if len(eventTimes) > 0:
			wait_time  = max(eventTimes)
			wait_time -= time.time()
			wait(wait_time + 5)
		wait_until_can_attack(session, city, island, travel_time)

	if island['barbarians']['destroyed'] == 1:
		# the barbarians are destroyed and can't be attacked
		resp = get_barbarians_info(session, island['id'])
		if 'barbarianCityCooldownTimer' in resp[2][1]:
			wait_time  = resp[2][1]['barbarianCityCooldownTimer']['countdown']['enddate']
			wait_time -= time.time()
			wait_time -= travel_time
			wait(wait_time + 5)
		wait_until_can_attack(session, city, island, travel_time)

def get_movements(session, city_id=None):
	if city_id is None:
		city_id = getCurrentCityId(session)
	query = {
		'view': 'militaryAdvisor',
		'oldView': 'updateGlobalData',
		'cityId': city_id,
		'backgroundView': 'city',
		'currentCityId': city_id,
		'templateView': 'militaryAdvisor',
		'actionRequest': actionRequest,
		'ajax': 1
	}

	resp = session.post(params=query)
	resp = json.loads(resp, strict=False)
	movements = resp[1][1][2]['viewScriptParams']['militaryAndFleetMovements']

	return movements

def get_current_attacks(session, city_id, island_id):

	movements = get_movements(session, city_id)
	curr_attacks = []

	for movement in movements:
		if movement['event']['mission'] != 13:
			continue
		if movement['target']['islandId'] != int(island_id):
			continue
		if movement['event']['isReturning'] != 0:
			continue
		if movement['origin']['cityId'] == -1:
			continue

		curr_attacks.append(movement)

	return curr_attacks

def wait_for_arrival(session, city, island):
	attacks = get_current_attacks(session, city['id'], island['id'])
	attacks = filter_loading(attacks) + filter_traveling(attacks)
	eventTimes = [ attack['eventTime'] for attack in attacks ]

	if len(eventTimes) == 0:
		return

	wait_time  = max(eventTimes)
	wait_time -= time.time()
	wait(wait_time + 5)

	wait_for_arrival(session, city, island)

def wait_for_round(session, city, island, travel_time, battle_start, round_number):
	if round_number == 1:
		wait_until_can_attack(session, city, island, travel_time)
	else:
		wait_time  = battle_start + (round_number - 2) * 15 * 60
		wait_time -= time.time()
		wait_time -= travel_time
		wait(wait_time + 5)

		if battle_start < time.time():
			html = session.get(island_url + city['id'])
			island = getIsland(html)
			assert island['barbarians']['underAttack'] == 1, "the battle ended before expected"

def calc_travel_time(city, island, speed):
	if city['x'] == island['x'] and city['y'] == island['y']:
		return math.ceil(36000/speed)
	else:
		return math.ceil(1200 * math.sqrt( ((city['x'] - island['x']) ** 2) + ((city['y'] - island['y']) ** 2) )) # lior fix

def filter_loading(attacks):
	return [ attack for attack in attacks if attack['event']['missionState'] == 1 ]

def filter_traveling(attacks):
	return [ attack for attack in attacks if attack['event']['missionState'] == 2 and attack['event']['canAbort'] ]

def filter_fighting(attacks):
	return [ attack for attack in attacks if attack['event']['missionState'] == 2 and attack['event']['canRetreat'] ]

def wait_until_attack_is_over(session, city, island):
	html = session.get(island_url + island['id'])
	island = getIsland(html)

	while island['barbarians']['destroyed'] == 0:

		attacks = get_current_attacks(session, city['id'], island['id'])
		# the attack probably failed
		if len(attacks) == 0:
			return

		eventTimes = [ attack['eventTime'] for attack in attacks ]
		wait_time  = min(eventTimes)
		wait_time -= time.time()
		wait(wait_time + 5)

		html = session.get(island_url + island['id'])
		island = getIsland(html)

def load_troops(session, city, island, attack_round, units_data, attack_data, extra_cargo=0):
	ships_needed = Decimal(extra_cargo) / Decimal(500)
	speeds = []
	current_units = get_units(session, city)
	for unit_id in attack_round['units']:
		amount_to_send = min(attack_round['units'][unit_id], current_units[unit_id]['amount'])
		attack_data['cargo_army_{}'.format(unit_id)] = amount_to_send

		if unit_id not in units_data:
			units_data[unit_id] = get_unit_data(session, city['id'], unit_id)

		speeds.append(units_data[unit_id]['speed'])

		if city_is_in_island(city, island) is False:
			weight = units_data[unit_id]['weight']
			ships_needed += Decimal(amount_to_send * weight) / Decimal(500)

	ships_needed = math.ceil(ships_needed)
	speed = min(speeds)
	travel_time = calc_travel_time(city, island, speed)
	return attack_data, ships_needed, travel_time

def loot(session, island, city, units_data, loot_round):
	while True:

		attack_data = {'action': 'transportOperations', 'function': 'attackBarbarianVillage', 'actionRequest': actionRequest, 'islandId': island['id'], 'destinationCityId': 0, 'cargo_army_304_upkeep': 3, 'cargo_army_304': 0, 'cargo_army_315_upkeep': 1, 'cargo_army_315': 0, 'cargo_army_302_upkeep': 4, 'cargo_army_302': 0, 'cargo_army_303_upkeep': 3, 'cargo_army_303': 0, 'cargo_army_312_upkeep': 15, 'cargo_army_312': 0, 'cargo_army_309_upkeep': 45, 'cargo_army_309': 0, 'cargo_army_307_upkeep': 15, 'cargo_army_307': 0, 'cargo_army_306_upkeep': 25, 'cargo_army_306': 0, 'cargo_army_305_upkeep': 30, 'cargo_army_305': 0, 'cargo_army_311_upkeep': 20, 'cargo_army_311': 0, 'cargo_army_310_upkeep': 10, 'cargo_army_310': 0, 'transporter': 0, 'barbarianVillage': 1, 'backgroundView': 'island', 'currentIslandId': island['id'], 'templateView': 'plunder', 'ajax': 1}

		# make sure we have ships on the port
		ships_available = waitForArrival(session)

		# if the barbarians are active again or all the resources were stolen, return
		html = session.get(island_url + island['id'])
		island = getIsland(html)
		destroyed = island['barbarians']['destroyed'] == 1
		resources = get_barbarians_lv(session, island)['resources']
		if destroyed is False or sum(resources) == 0:
			return

		# if we already sent an attack and we still have ships on the port, it was the last one
		attacks = get_current_attacks(session, city['id'], island['id'])
		attacks = filter_loading(attacks) + filter_traveling(attacks)
		if len(attacks) > 0:
			return

		attack_data, ships_needed, travel_time = load_troops(session, city, island, attack_round, units_data, attack_data, sum(resources))
		attack_data['transporter'] = min(ships_available, ships_needed)

		# make sure we have time to send the attack
		time_left = None
		resp = get_barbarians_info(session, island['id'])
		if 'barbarianCityCooldownTimer' in resp[2][1]:
			time_left  = resp[2][1]['barbarianCityCooldownTimer']['countdown']['enddate']
			time_left -= time.time()
		if time_left is not None and travel_time > time_left:
			return

		# send attack
		session.post(payloadPost=attack_data)

def do_it(session, island, city, babarians_info, plan):

	units_data = {}

	battle_start = None

	for attack_round in plan:

		# this round is supposed to get the resources
		if attack_round['loot']:
			break

		attack_data = {'action': 'transportOperations', 'function': 'attackBarbarianVillage', 'actionRequest': actionRequest, 'islandId': island['id'], 'destinationCityId': 0, 'cargo_army_304_upkeep': 3, 'cargo_army_304': 0, 'cargo_army_315_upkeep': 1, 'cargo_army_315': 0, 'cargo_army_302_upkeep': 4, 'cargo_army_302': 0, 'cargo_army_303_upkeep': 3, 'cargo_army_303': 0, 'cargo_army_312_upkeep': 15, 'cargo_army_312': 0, 'cargo_army_309_upkeep': 45, 'cargo_army_309': 0, 'cargo_army_307_upkeep': 15, 'cargo_army_307': 0, 'cargo_army_306_upkeep': 25, 'cargo_army_306': 0, 'cargo_army_305_upkeep': 30, 'cargo_army_305': 0, 'cargo_army_311_upkeep': 20, 'cargo_army_311': 0, 'cargo_army_310_upkeep': 10, 'cargo_army_310': 0, 'transporter': 0, 'barbarianVillage': 1, 'backgroundView': 'island', 'currentIslandId': island['id'], 'templateView': 'plunder', 'ajax': 1}

		attack_data, ships_needed, travel_time = load_troops(session, city, island, attack_round, units_data, attack_data)

		try:
			wait_for_round(session, city, island, travel_time, battle_start, attack_round['round'])
		except AssertionError:
			# battle ended before expected
			break

		ships_available = waitForArrival(session)
		while ships_available < ships_needed:
			ships_available = waitForArrival(session)
		ships_available -= ships_needed

		# if the number of available troops changed, the POST request might not work as intended

		attack_data['transporter'] = min(babarians_info['ships'], attack_round['ships'], ships_available)

		# send new round
		session.post(payloadPost=attack_data)

		if attack_round['round'] == 1:
			battle_start = time.time() + travel_time

	wait_until_attack_is_over(session, city, island)

	last_round = plan[-1]
	if last_round['loot']:
		loot(session, city, island, units_data, last_round)
