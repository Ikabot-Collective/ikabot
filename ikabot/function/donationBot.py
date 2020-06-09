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
from ikabot.helpers.getJson import getCity
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
				print(_('What is the maximum percentage of your storage capacity that you whish to keep occupied? (the resources that exceed it, will be donated) (default: 80%)'))
				percentage = read(min=0, max=100, empty=True)
				if percentage == '':
					percentage = 80
				elif percentage == 100: # if the user is ok with the storage beeing totally full, don't donate at all
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
		city = getCity(html)
		cities_dict[cityId]['island'] = city['islandId']

	while True:
		for cityId in cities_ids:
			donation_type = cities_dict[cityId]['donation_type']
			if donation_type is None:
				continue

			# get the storageCapacity and the wood this city has
			html = s.get(urlCiudad + cityId)
			city = getCity(html)
			wood = city['recursos'][0]
			storageCapacity = city['storageCapacity']

			# get the percentage
			percentage = cities_dict[cityId]['percentage']
			percentage /= 100

			# calculate what is the amount of wood that should be preserved
			max_wood = storageCapacity * percentage
			max_wood = int(max_wood)

			# calculate the wood that is exceeding the percentage
			to_donate = wood - max_wood
			if to_donate <= 0:
				continue

			islandId = cities_dict[cityId]['island']

			# donate
			s.post(payloadPost={'islandId': islandId, 'type': donation_type, 'action': 'IslandScreen', 'function': 'donate', 'donation': to_donate, 'backgroundView': 'island', 'templateView': donation_type, 'actionRequest': 'REQUESTID', 'ajax': '1'})

		msg = _('I donated automatically.')
		sendToBotDebug(s, msg, debugON_donationBot)

		# sleep a day
		wait(24*60*60, maxrandom=60*60)
