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
from ikabot.helpers.recursos import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import getCity

t = gettext.translation('getStatus', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

def getStatus(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()
		color_arr = [bcolors.ENDC, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]

		print(_('Ships {:d}/{:d}').format(getAvailableShips(s), getTotalShips(s)))

		print(_('\nOf which city do you want to see the state?'))
		city = chooseCity(s)
		banner()

		(wood, good, typeGood) = getProduccionPerSecond(s, city['id'])
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
			print('{} {}{}{} '.format(materials_names[i], bcolors.ENDC, color_resources[i], addDot(resources[i])), end='')
		print('')

		print(_('Production:'))
		print('{}:{} {}:{}'.format(materials_names[0], addDot(wood*3600), materials_names[typeGood], addDot(good*3600)))

		hasTavern = 'tavern' in [ building['building'] for building in city['position'] ]
		if hasTavern:
			consume_per_hour = city['consumo']
			if consume_per_hour == 0:
				print(_('{}{}Does not consume wine!{}').format(bcolors.RED, bcolors.BOLD, bcolors.ENDC))
			else:
				if typeGood == 1 and (good*3600) > consume_per_hour:
					time_lapse = '∞'
				else:
					consumoXseg = Decimal(consume_per_hour) / Decimal(3600)
					segsRestantes = Decimal(resources[1]) / Decimal(consumoXseg)
					time_lapse = daysHoursMinutes(segsRestantes)
				print(_('There is wine for: {}').format(time_lapse))

		for edificio in [ edificio for edificio in city['position'] if edificio['name'] != 'empty' ]:
			if edificio['isMaxLevel'] is True:
				color = bcolors.BLACK
			elif edificio['canUpgrade'] is True:
				color = bcolors.GREEN
			else:
				color = bcolors.RED

			level = edificio['level']
			if level < 10:
				level = ' ' + str(level)
			else:
				level = str(level)
			if edificio['isBusy'] is True:
				level = level + '+'

			print(_('lv:{}\t{}{}{}').format(level, color, edificio['name'], bcolors.ENDC))

		enter()
		print('')
		e.set()
	except KeyboardInterrupt:
		e.set()
		return
