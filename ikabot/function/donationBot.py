#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import wait
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.recursos import getRecursosDisponibles

t = gettext.translation('donationBot', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def donationBot(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()
		(cities_ids, cities) = getIdsOfCities(s)
		cities_dict = {}
		initials = [ material_name[0] for material_name in materials_names ]
		for cityId in cities_ids:
			tradegood = cities[cityId]['tradegood']
			initial = initials[int(tradegood)]
			print(_('In {} ({}), Do you wish to donate to the forest, to the trading good or neither? [f/t/n]').format(cities[cityId]['name'], initial))
			f = _('f')
			t = _('t')
			n = _('n')

			rta = read(values=[f, f.upper(), t, t.upper(), n, n.upper()])
			if rta.lower() == f:
				donation_type = 'resource'
			elif rta.lower() == t:
				donation_type = 'tradegood'
			else:
				donation_type = None
				percentage = None

			if donation_type is not None:
				print(_('What percentage of the resources do you want to donate every day? (default: 100%)'))
				percentage = read(min=0, max=100, empty=True)
				if percentage == '':
					percentage = 100
				elif percentage == 0:
					donation_type = None

			cities_dict[cityId] = {'donation_type': donation_type, 'percentage': percentage}

		print(_('I will donate every day.'))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI donate every day\n')
	setInfoSignal(s, info)
	try:
		do_it(s, cities_ids, cities_dict)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def do_it(s, cities_ids, cities_dict):
	for cityId in cities_ids:
		html = s.get(urlCiudad + cityId)
		city = getCiudad(html)
		cities_dict[cityId]['island'] = city['islandId']

	while True:
		for cityId in cities_ids:
			donation_type = cities_dict[cityId]['donation_type']
			if donation_type is None:
				continue

			html = s.get(urlCiudad + cityId)
			wood  = getRecursosDisponibles(html, num=True)[0]
			wood *= ( cities_dict[cityId]['percentage'] / 100 )
			wood = int(wood)
			islandId = cities_dict[cityId]['island']

			s.post(payloadPost={'islandId': islandId, 'type': donation_type, 'action': 'IslandScreen', 'function': 'donate', 'donation': wood, 'backgroundView': 'island', 'templateView': donation_type, 'actionRequest': 'REQUESTID', 'ajax': '1'})

		msg = _('I donated automatically.')
		sendToBotDebug(s, msg, debugON_donationBot)

		# sleep a day
		wait(24*60*60, maxrandom=60*60)
