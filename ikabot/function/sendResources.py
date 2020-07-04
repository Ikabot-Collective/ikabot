#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import executeRoutes
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCity
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.varios import addDot
from ikabot.helpers.resources import *

t = gettext.translation('sendResources',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def sendResources(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	try:
		routes = []
		while True:

			banner()
			print(_('Origin city:'))
			try:
				cityO = chooseCity(session)
			except KeyboardInterrupt:
				if routes:
					print(_('Send shipment? [Y/n]'))
					rta = read(values=['y', 'Y', 'n', 'N', ''])
					if rta.lower() != 'n':
						break
				event.set()
				return

			banner()
			print(_('Destination city'))
			cityD = chooseCity(session, foreign=True)
			idIsland = cityD['islandId']

			if cityO['id'] == cityD['id']:
				continue

			resources_left = cityO['recursos']
			for route in routes:
				(origin_city, destination_city, __, *toSend) = route
				if origin_city['id'] == cityO['id']:
					for i in range(len(materials_names)):
						resources_left[i] -= toSend[i]

				# the destination city might be from another player
				if cityD['propia'] and destination_city['id'] == cityD['id']:
					for i in range(len(materials_names)):
						cityD['freeSpaceForResources'][i] -= toSend[i]

			banner()
			# the destination city might be from another player
			if cityD['propia']:
				msg = ''
				for i in range(len(materials_names)):
					if resources_left[i] > cityD['freeSpaceForResources'][i]:
						msg += '{} more {}\n'.format(addDot(cityD['freeSpaceForResources'][i]), materials_names[i].lower())

				if len(msg) > 0:
					print(_('You can store just:\n{}').format(msg))

			print(_('Available:'))
			for i in range(len(materials_names)):
				print('{}:{} '.format(materials_names[i], addDot(resources_left[i])), end='')
			print('')

			print(_('Send:'))
			try:
				max_name = max( [ len(material) for material in materials_names ] )
				send = []
				for i in range(len(materials_names)):
					material_name = materials_names[i]
					pad = ' ' * ( max_name - len(material_name) )
					val = askForValue(_('{}{}:'.format(pad, material_name)), resources_left[i])
					send.append(val)
			except KeyboardInterrupt:
				continue
			if sum(send) == 0:
				continue

			banner()
			print(_('About to send from {} to {}').format(cityO['cityName'], cityD['cityName']))
			for i in range(len(materials_names)):
				if send[i] > 0:
					print('{}:{} '.format(materials_names[i], addDot(send[i])), end='')
			print('')

			print(_('Proceed? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() != 'n':
				route = (cityO, cityD, idIsland, *send)
				routes.append(route)
				print(_('Create another shipment? [y/N]'))
				rta = read(values=['y', 'Y', 'n', 'N', ''])
				if rta.lower() != 'y':
					break
	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nSend resources\n')

	setInfoSignal(session, info)
	try:
		executeRoutes(session, routes)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()
