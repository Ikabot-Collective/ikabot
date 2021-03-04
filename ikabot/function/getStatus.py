#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import gettext
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.varios import *
from ikabot.helpers.resources import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.market import getGold

t = gettext.translation('getStatus',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

def getStatus(session, event, stdin_fd):
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
		color_arr = [bcolors.ENDC, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]

		(ids, __) = getIdsOfCities(session)
		total_resources = [0] * len(materials_names)
		total_production = [0] * len(materials_names)
		total_wine_consumption = 0
		available_ships = 0
		total_ships = 0
		for id in ids:
			session.get('view=city&cityId={}'.format(id), noIndex = True)
			data = session.get("view=updateGlobalData&ajax=1", noIndex = True)
			json_data = json.loads(data, strict=False)
			json_data = json_data[0][1]['headerData']
			if json_data['relatedCity']['owncity'] != 1:
				continue
			wood = Decimal( json_data['resourceProduction'] )
			good = Decimal( json_data['tradegoodProduction'] )
			typeGood = int( json_data['producedTradegood'] )
			total_production[0] += wood * 3600
			total_production[typeGood] += good * 3600
			total_wine_consumption += json_data['wineSpendings']
			total_resources[0] += json_data['currentResources']['resource']
			total_resources[1] += json_data['currentResources']['1']
			total_resources[2] += json_data['currentResources']['2']
			total_resources[3] += json_data['currentResources']['3']
			total_resources[4] += json_data['currentResources']['4']
			available_ships = json_data['freeTransporters']
			total_ships = json_data['maxTransporters']
			total_gold = int(Decimal(json_data['gold']))
			total_gold_production = int(Decimal(json_data['scientistsUpkeep'] + json_data['income'] + json_data['upkeep']))
		print(_('Ships {:d}/{:d}').format(int(available_ships), int(total_ships)))
		print(_("\nTotal:"))
		print('{:>10}'.format(' '), end='|')
		for i in range(len(materials_names)):
			print('{:>12}'.format(materials_names_english[i]), end = '|')
		print()
		print('{:>10}'.format('Available'), end = '|')
		for i in range(len(materials_names)):
			print('{:>12}'.format(addThousandSeparator(total_resources[i], ' ')), end = '|')
		print()
		print('{:>10}'.format('Production'), end = '|')
		for i in range(len(materials_names)):
			print('{:>12}'.format(addThousandSeparator(total_production[i], ' ')), end = '|')
		print()
		print("Gold : {}, Gold production : {}".format(addThousandSeparator(total_gold, ' '), addThousandSeparator(total_gold_production, ' ')))
		print("Wine consumption : {}".format(addThousandSeparator(total_wine_consumption, ' ')), end='')


		print(_('\nOf which city do you want to see the state?'))
		city = chooseCity(session)
		banner()

		(wood, good, typeGood) = getProductionPerSecond(session, city['id'])
		print('\033[1m{}{}{}'.format(color_arr[int(typeGood)], city['cityName'], color_arr[0]))

		resources = city['recursos']
		storageCapacity = city['storageCapacity']
		color_resources = []
		for i in range(len(materials_names)):
			if resources[i] == storageCapacity:
				color_resources.append(bcolors.RED)
			else:
				color_resources.append(bcolors.ENDC)
		print(_('Storage:'))
		print(addThousandSeparator(storageCapacity))
		print(_('Resources:'))
		for i in range(len(materials_names)):
			print('{} {}{}{} '.format(materials_names[i], color_resources[i], addThousandSeparator(resources[i]), bcolors.ENDC), end='')
		print('')

		print(_('Production:'))
		print('{}:{} {}:{}'.format(materials_names[0], addThousandSeparator(wood*3600), materials_names[typeGood], addThousandSeparator(good*3600)))

		hasTavern = 'tavern' in [ building['building'] for building in city['position'] ]
		if hasTavern:
			consumption_per_hour = city['consumo']
			if consumption_per_hour == 0:
				print(_('{}{}Does not consume wine!{}').format(bcolors.RED, bcolors.BOLD, bcolors.ENDC))
			else:
				if typeGood == 1 and (good*3600) > consumption_per_hour:
					elapsed_time_run_out = '∞'
				else:
					consumption_per_second = Decimal(consumption_per_hour) / Decimal(3600)
					remaining_resources_to_consume = Decimal(resources[1]) / Decimal(consumption_per_second)
					elapsed_time_run_out = daysHoursMinutes(remaining_resources_to_consume)
				print(_('There is wine for: {}').format(elapsed_time_run_out))

		for building in [ building for building in city['position'] if building['name'] != 'empty' ]:
			if building['isMaxLevel'] is True:
				color = bcolors.BLACK
			elif building['canUpgrade'] is True:
				color = bcolors.GREEN
			else:
				color = bcolors.RED

			level = building['level']
			if level < 10:
				level = ' ' + str(level)
			else:
				level = str(level)
			if building['isBusy'] is True:
				level = level + '+'

			print(_('lv:{}\t{}{}{}').format(level, color, building['name'], bcolors.ENDC))

		enter()
		print('')
		event.set()
	except KeyboardInterrupt:
		event.set()
		return
