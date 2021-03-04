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
from ikabot.helpers.resources import *
from ikabot.helpers.botComm import *

t = gettext.translation('alertLowWine',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

def alertLowWine(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	try:
		if checkTelegramData(session) is False:
			event.set()
			return
		banner()
		hours = read(msg=_('How many hours should be left until the wine runs out in a city so that it\'s alerted?'), min=1)
		print(_('It will be alerted when the wine runs out in less than {:d} hours in any city').format(hours))
		enter()
	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI alert if the wine runs out in less than {:d} hours\n').format(hours)
	setInfoSignal(session, info)
	try:
		do_it(session, hours)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def do_it(session, hours):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	hours : int
	"""

	was_alerted = {}
	while True:
		# getIdsOfCities is called on a loop because the amount of cities may change
		ids, cities = getIdsOfCities(session)

		for cityId in cities:
			if cityId not in was_alerted:
				was_alerted[cityId] = False

		for cityId in cities:
			html = session.get(city_url + cityId)
			city = getCity(html)

			# if the city doesn't even have a tavern built, ignore it
			if 'tavern' not in [ building['building'] for building in city['position'] ]:
				continue

			consumption_per_hour = city['consumo']

			# is a wine city
			if cities[cityId]['tradegood'] == '1':
				wine_production = getProductionPerSecond(session, cityId)[1]
				wine_production = wine_production * 60 * 60
				if consumption_per_hour > wine_production:
					consumption_per_hour -= wine_production
				else:
					was_alerted[cityId] = False
					continue

			consumption_per_seg = Decimal(consumption_per_hour) / Decimal(3600)
			wine_available = city['recursos'][1]

			if consumption_per_seg == 0:
				if was_alerted[cityId] is False:
					msg = _('The city {} is not consuming wine!').format(city['name'])
					sendToBot(session, msg)
					was_alerted[cityId] = True
				continue

			seconds_left = Decimal(wine_available) / Decimal(consumption_per_seg)
			if seconds_left < hours*60*60:
				if was_alerted[cityId] is False:
					time_left = daysHoursMinutes(seconds_left)
					msg = _('In {}, the wine will run out in {}').format(time_left, city['name'])
					sendToBot(session, msg)
					was_alerted[cityId] = True
			else:
				was_alerted[cityId] = False

		time.sleep(20*60)
