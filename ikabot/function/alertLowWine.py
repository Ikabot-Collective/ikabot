#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import traceback
import gettext
from decimal import *
from ikabot.config import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import getIdsOfCities
from ikabot.helpers.varios import daysHoursMinutes
from ikabot.helpers.getJson import getCity
from ikabot.helpers.recursos import *
from ikabot.helpers.botComm import *

t = gettext.translation('alertLowWine',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

def alertLowWine(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		if checkTelegramData(s) is False:
			e.set()
			return
		banner()
		hours = read(msg=_('How many hours should be left until the wine runs out in a city so that it\'s alerted?'), min=1)
		print(_('It will be alerted when the wine runs out in less than {:d} hours in any city').format(hours))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI alert if the wine runs out in less than {:d} hours\n').format(hours)
	setInfoSignal(s, info)
	try:
		do_it(s, hours)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def do_it(s, hours):
	ids, cities = getIdsOfCities(s)
	while True:
		# getIdsOfCities is called on a loop because the amount of cities may change
		ids, cities_new = getIdsOfCities(s)
		if len(cities_new) != len(cities):
			cities = cities_new

		for cityId in cities:
			if 'reported' not in cities[cityId]:
				cities[cityId]['reported'] = False

		for cityId in cities:
			html = s.get(urlCiudad + cityId)
			city = getCity(html)

			# if the city doesn't even have a tavern built, ignore it
			if 'tavern' not in [ building['building'] for building in city['position'] ]:
				continue

			consumption_per_hour = city['consumo']

			# is a wine city
			if cities[cityId]['tradegood'] == '1':
				wine_production = getProduccionPerSecond(s, cityId)[1]
				wine_production = wine_production * 60 * 60
				if consumption_per_hour > wine_production:
					consumption_per_hour -= wine_production
				else:
					continue

			consumption_per_seg = Decimal(consumption_per_hour) / Decimal(3600)
			wine_available = city['recursos'][1]

			if consumption_per_seg == 0:
				if cities[cityId]['reported'] is False:
					msg = _('The city {} is not consuming wine!').format(city['name'])
					sendToBot(s, msg)
					cities[cityId]['reported'] = True
				continue

			seconds_left = Decimal(wine_available) / Decimal(consumption_per_seg)
			if seconds_left < hours*60*60:
				if cities[cityId]['reported'] is False:
					time_left = daysHoursMinutes(seconds_left)
					msg = _('In {}, the wine will run out in {}').format(time_left, city['name'])
					sendToBot(s, msg)
					cities[cityId]['reported'] = True
			else:
				cities[cityId]['reported'] = False

		time.sleep(20*60)
