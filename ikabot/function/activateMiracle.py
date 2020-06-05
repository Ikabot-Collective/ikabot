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
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal

t = gettext.translation('activateMiracle',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def obtenerMilagrosDisponibles(s):
	idsIslas = getIdsOfIslands(s)
	islas = []
	for idIsla in idsIslas:
		html = s.get(urlIsla + idIsla)
		isla = getIsla(html)
		isla['activable'] = False
		islas.append(isla)

	ids, citys = getIdsOfCities(s)
	for ciudad in citys:
		city = citys[ciudad]
		wonder = [ isla['wonder'] for isla in islas if city['coords'] == '[{}:{}] '.format(isla['x'], isla['y']) ][0]
		if wonder in [ isla['wonder'] for isla in islas if isla['activable'] ]:
			continue

		html = s.get(urlCiudad + str(city['id']))
		ciudad = getCiudad(html)

		if 'temple' in [ edificio['building'] for edificio in ciudad['position'] ]:
			for i in range( len( ciudad['position'] ) ):
				if ciudad['position'][i]['building'] == 'temple':
					ciudad['pos'] = str(i)
					break

			params = {"view": "temple", "cityId": ciudad['id'], "position": ciudad['pos'], "backgroundView": "city", "currentCityId": ciudad['id'], "actionRequest": s.token(), "ajax": "1"}
			data = s.post(params=params)
			data = json.loads(data, strict=False)
			available =  data[2][1]['js_WonderViewButton']['buttonState'] == 'enabled'
			if available is False:
				data = data[2][1]
				for elem in data:
					if 'countdown' in data[elem]:
						enddate     = data[elem]['countdown']['enddate']
						currentdate = data[elem]['countdown']['currentdate']
						break

			for isla in islas:
				if isla['id'] == ciudad['islandId']:
					isla['activable'] = True
					isla['ciudad'] = ciudad
					isla['available'] = available
					if available is False:
						isla['available_in'] = enddate - currentdate
					break

	return [ isla for isla in islas if isla['activable'] ]

def activateMiracleImpl(s, isla):
	params = {'action': 'CityScreen', 'cityId': isla['ciudad']['id'], 'function': 'activateWonder', 'position': isla['ciudad']['pos'], 'backgroundView': 'city', 'currentCityId': isla['ciudad']['id'], 'templateView': 'temple', 'actionRequest': s.token(), 'ajax': '1'}
	rta = s.post(params=params)
	return json.loads(rta, strict=False)

def elegir_isla(islas):
	print(_('Which miracle do you want to activate?'))
	i = 0
	print(_('(0) Exit'))
	for isla in islas:
		i += 1
		if isla['available']:
			print('({:d}) {}'.format(i, isla['wonderName']))
		else:
			print(_('({:d}) {} (available in: {})').format(i, isla['wonderName'], daysHoursMinutes(isla['available_in'])))

	index = read(min=0, max=i)
	if index == 0:
		return None
	isla = islas[index - 1]
	return isla

def activateMiracle(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		islas = obtenerMilagrosDisponibles(s)
		if islas == []:
			print(_('There are no miracles available.'))
			enter()
			e.set()
			return

		isla = elegir_isla(islas)
		if isla is None:
			e.set()
			return

		if isla['available']:
			print(_('\nThe miracle {} will be activated').format(isla['wonderName']))
			print(_('Proceed? [Y/n]'))
			r = read(values=['y', 'Y', 'n', 'N', ''])
			if r.lower() == 'n':
				e.set()
				return

			rta = activateMiracleImpl(s, isla)

			if rta[1][1][0] == 'error':
				print(_('The miracle {} could not be activated.').format(isla['wonderName']))
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

			print(_('The miracle {} was activated.').format(isla['wonderName']))
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
			print(_('\nThe miracle {} will be activated in {}').format(isla['wonderName'], daysHoursMinutes(isla['available_in'])))
			print(_('Proceed? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				e.set()
				return
			wait_time = isla['available_in']
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

	info = _('\nI activate the miracle {} {:d} times\n').format(isla['wonderName'], iterations)
	setInfoSignal(s, info)
	try:
		do_it(s, isla, iterations)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def wait_for_miracle(s, isla):
	while True:
		params = {"view": "temple", "cityId": isla['ciudad']['id'], "position": isla['ciudad']['pos'], "backgroundView": "city", "currentCityId": isla['ciudad']['id'], "actionRequest": s.token(), "ajax": "1"}
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
