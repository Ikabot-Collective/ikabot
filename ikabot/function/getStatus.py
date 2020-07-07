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

		print(_('Ships {:d}/{:d}').format(getAvailableShips(session), getTotalShips(session)))

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
		print(addDot(storageCapacity))
		print(_('Resources:'))
		for i in range(len(materials_names)):
			print('{} {}{}{} '.format(materials_names[i], color_resources[i], addDot(resources[i]), bcolors.ENDC), end='')
		print('')

		print(_('Production:'))
		print('{}:{} {}:{}'.format(materials_names[0], addDot(wood*3600), materials_names[typeGood], addDot(good*3600)))

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
