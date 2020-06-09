#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.getJson import getCity
from ikabot.helpers.signals import setInfoSignal

t = gettext.translation('activateMiracle',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def obtainMiraclesAvailable(s):
	idsIslands = getIslandsIds(s)
	islands = []
	for idIsland in idsIslands:
		html = s.get(urlIsla + idIsland)
		isla = getIsland(html)
		isla['activable'] = False
		islands.append(isla)

	ids, citys = getIdsOfCities(s)
	for cityId in citys:
		city = citys[cityId]
		# get the wonder for this city
		wonder = [ island['wonder'] for island in islands if city['coords'] == '[{}:{}] '.format(island['x'], island['y']) ][0]
		# if the wonder is not new, continue
		if wonder in [ island['wonder'] for island in islands if island['activable'] ]:
			continue

		html = s.get(urlCiudad + str(city['id']))
		city = getCity(html)

		# make sure that the city has a temple
		for i in range( len( city['position'] ) ):
			if city['position'][i]['building'] == 'temple':
				city['pos'] = str(i)
				break
		else:
			continue

		# get wonder information
		params = {"view": "temple", "cityId": city['id'], "position": city['pos'], "backgroundView": "city", "currentCityId": city['id'], "actionRequest": "REQUESTID", "ajax": "1"}
		data = s.post(params=params)
		data = json.loads(data, strict=False)
		data = data[2][1]
		available =  data['js_WonderViewButton']['buttonState'] == 'enabled'
		if available is False:
			for elem in data:
				if 'countdown' in data[elem]:
					enddate     = data[elem]['countdown']['enddate']
					currentdate = data[elem]['countdown']['currentdate']
					break

		# set the information on the island which wonder we can activate
		for isla in islands:
			if isla['id'] == city['islandId']:
				isla['activable'] = True
				isla['ciudad'] = city
				isla['available'] = available
				if available is False:
					isla['available_in'] = enddate - currentdate
				break

	# only return island which wonder we can activate
	return [ island for island in islands if island['activable'] ]

def activateMiracleImpl(s, isla):
	params = {'action': 'CityScreen', 'cityId': isla['ciudad']['id'], 'function': 'activateWonder', 'position': isla['ciudad']['pos'], 'backgroundView': 'city', 'currentCityId': isla['ciudad']['id'], 'templateView': 'temple', 'actionRequest': 'REQUESTID', 'ajax': '1'}
	rta = s.post(params=params)
	return json.loads(rta, strict=False)

def chooseIsland(islands):
	print(_('Which miracle do you want to activate?'))
	i = 0
	print(_('(0) Exit'))
	for island in islands:
		i += 1
		if island['available']:
			print('({:d}) {}'.format(i, island['wonderName']))
		else:
			print(_('({:d}) {} (available in: {})').format(i, island['wonderName'], daysHoursMinutes(island['available_in'])))

	index = read(min=0, max=i)
	if index == 0:
		return None
	island = islands[index - 1]
	return island

def activateMiracle(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		islands = obtainMiraclesAvailable(s)
		if islands == []:
			print(_('There are no miracles available.'))
			enter()
			e.set()
			return

		island = chooseIsland(islands)
		if island is None:
			e.set()
			return

		if island['available']:
			print(_('\nThe miracle {} will be activated').format(island['wonderName']))
			print(_('Proceed? [Y/n]'))
			r = read(values=['y', 'Y', 'n', 'N', ''])
			if r.lower() == 'n':
				e.set()
				return

			rta = activateMiracleImpl(s, island)

			if rta[1][1][0] == 'error':
				print(_('The miracle {} could not be activated.').format(island['wonderName']))
				enter()
				e.set()
				return

			data = rta[2][1]
			for elem in data:
				if 'countdown' in data[elem]:
					enddate     = data[elem]['countdown']['enddate']
					currentdate = data[elem]['countdown']['currentdate']
					break
			wait_time = enddate - currentdate

			print(_('The miracle {} was activated.').format(island['wonderName']))
			enter()
			banner()

			while True:
				print(_('Do you wish to activate it again when it is finished? [y/N]'))

				r = read(values=['y', 'Y', 'n', 'N', ''])
				if r.lower() != 'y':
					e.set()
					return

				iterations = read(msg=_('How many times?: '), digit=True, min=0)

				if iterations == 0:
					e.set()
					return

				duration = wait_time * iterations

				print(_('It will finish in:{}').format(daysHoursMinutes(duration)))

				print(_('Proceed? [Y/n]'))
				r = read(values=['y', 'Y', 'n', 'N', ''])
				if r.lower() == 'n':
					banner()
					continue
				break
		else:
			print(_('\nThe miracle {} will be activated in {}').format(island['wonderName'], daysHoursMinutes(island['available_in'])))
			print(_('Proceed? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				e.set()
				return
			wait_time = island['available_in']
			iterations = 1

			print(_('\nThe mirable will be activated.'))
			enter()
			banner()

			while True:
				print(_('Do you wish to activate it again when it is finished? [y/N]'))

				r = read(values=['y', 'Y', 'n', 'N', ''])
				again = r.lower() == 'y'
				if again is True:
					try:
						iterations = read(msg=_('How many times?: '), digit=True, min=0)
					except KeyboardInterrupt:
						iterations = 1
						break

					if iterations == 0:
						iterations = 1
						break

					iterations += 1
					duration = wait_time * iterations
					print(_('It is not possible to calculate the time of finalization. (at least: {})').format(daysHoursMinutes(duration)))
					print(_('Proceed? [Y/n]'))

					try:
						r = read(values=['y', 'Y', 'n', 'N', ''])
					except KeyboardInterrupt:
						iterations = 1
						break

					if r.lower() == 'n':
						iterations = 1
						banner()
						continue
				break
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI activate the miracle {} {:d} times\n').format(island['wonderName'], iterations)
	setInfoSignal(s, info)
	try:
		do_it(s, island, iterations)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def wait_for_miracle(s, isla):
	while True:
		params = {"view": "temple", "cityId": isla['ciudad']['id'], "position": isla['ciudad']['pos'], "backgroundView": "city", "currentCityId": isla['ciudad']['id'], "actionRequest": "REQUESTID", "ajax": "1"}
		data = s.post(params=params)
		data = json.loads(data, strict=False)
		data = data[2][1]

		for elem in data:
			if 'countdown' in data[elem]:
				enddate     = data[elem]['countdown']['enddate']
				currentdate = data[elem]['countdown']['currentdate']
				wait_time = enddate - currentdate
				break
		else:
			available = data['js_WonderViewButton']['buttonState'] == 'enabled'
			if available:
				return
			else:
				wait_time = 60

		msg = _('I wait {:d} seconds to activate the miracle {}').format(wait_time, isla['wonderName'])
		sendToBotDebug(s, msg, debugON_activateMiracle)
		wait(wait_time + 5)

def do_it(s, isla, iterations):

	for i in range(iterations):

		wait_for_miracle(s, isla)

		rta = activateMiracleImpl(s, isla)

		if rta[1][1][0] == 'error':
			msg = _('The miracle {} could not be activated.').format(isla['wonderName'])
			sendToBot(s, msg)
			return

		msg = _('Miracle {} successfully activated').format(isla['wonderName'])
		sendToBotDebug(s, msg, debugON_activateMiracle)
