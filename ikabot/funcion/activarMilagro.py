#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import forkear
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal

t = gettext.translation('activarMilagro',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def obtenerMilagrosDisponibles(s):
	idsIslas = getIdsdeIslas(s)
	islas = []
	for idIsla in idsIslas:
		html = s.get(urlIsla + idIsla)
		isla = getIsla(html)
		isla['activable'] = False
		islas.append(isla)

	ids, citys = getIdsDeCiudades(s)
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

def activarMilagroImpl(s, isla):
	params = {'action': 'CityScreen', 'cityId': isla['ciudad']['id'], 'function': 'activateWonder', 'position': isla['ciudad']['pos'], 'backgroundView': 'city', 'currentCityId': isla['ciudad']['id'], 'templateView': 'temple', 'actionRequest': s.token(), 'ajax': '1'}
	rta = s.post(params=params)
	return json.loads(rta, strict=False)

def elegir_isla(islas):
	print(_('¿Qué milagro quiere activar?'))
	i = 0
	print(_('(0) Salir'))
	for isla in islas:
		i += 1
		if isla['available']:
			print('({:d}) {}'.format(i, isla['wonderName']))
		else:
			print(_('({:d}) {} (disponible en: {})').format(i, isla['wonderName'], diasHorasMinutos(isla['available_in'])))

	index = read(min=0, max=i)
	if index == 0:
		return None
	isla = islas[index - 1]
	return isla

def activarMilagro(s):
	banner()

	islas = obtenerMilagrosDisponibles(s)
	if islas == []:
		print(_('No existen milagros disponibles.'))
		enter()
		return

	isla = elegir_isla(islas)
	if isla is None:
		return

	if isla['available']:
		print(_('\nSe activará el milagro {}').format(isla['wonderName']))
		print(_('¿Proceder? [Y/n]'))
		r = read(values=['y', 'Y', 'n', 'N', ''])
		if r.lower() == 'n':
			return

		rta = activarMilagroImpl(s, isla)

		if rta[1][1][0] == 'error':
			print(_('No se pudo activar el milagro {}.').format(isla['wonderName']))
			enter()
			return

		data = rta[2][1]
		for elem in data:
			if 'countdown' in data[elem]:
				enddate     = data[elem]['countdown']['enddate']
				currentdate = data[elem]['countdown']['currentdate']
				break
		wait_time   = enddate - currentdate

		print(_('Se activó el milagro {}.').format(isla['wonderName']))
		enter()
		banner()

		while True:
			print(_('¿Desea activarlo nuevamente al terminar? [y/N]'))

			r = read(values=['y', 'Y', 'n', 'N', ''])
			if r.lower() != 'y':
				return

			iterations = read(msg=_('¿Cuántas veces?: '), digit=True, min=0)

			if iterations == 0:
				return


			duration = wait_time * iterations

			print(_('Terminará en:{}').format(diasHorasMinutos(duration)))

			print(_('¿Proceder? [Y/n]'))
			r = read(values=['y', 'Y', 'n', 'N', ''])
			if r.lower() == 'n':
				banner()
				continue
			break
	else:
		print(_('\nSe activará el milagro {} en {}').format(isla['wonderName'], diasHorasMinutos(isla['available_in'])))
		print(_('¿Proceder? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			return
		wait_time = isla['available_in']
		iterations = 1

		print(_('\nSe activará el milagro.'))
		enter()
		banner()

		while True:
			print(_('¿Desea activarlo nuevamente al terminar? [y/N]'))

			r = read(values=['y', 'Y', 'n', 'N', ''])
			again = r.lower() == 'y'
			if again is True:
				try:
					iterations = read(msg=_('¿Cuántas veces?: '), digit=True, min=0)
				except KeyboardInterrupt:
					iterations = 1
					break

				if iterations == 0:
					iterations = 1
					break

				iterations += 1
				duration = wait_time * iterations
				print(_('No se puede calcular el momento de finalización. (por lo menos: {}').format(diasHorasMinutos(duration)))
				print(_('¿Proceder? [Y/n]'))

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

	forkear(s)
	if s.padre is True:
		return

	info = _('\nActivo el milagro {} {:d} veces\n').format(isla['wonderName'], iterations)
	setInfoSignal(s, info)
	try:
		do_it(s, isla, wait_time, iterations)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def do_it(s, isla, wait_time, iterations):

	times_activated = 0
	while times_activated < iterations:
		esperar(wait_time + 5)

		rta = activarMilagroImpl(s, isla)

		if rta[1][1][0] == 'error':
			msg = _('No se pudo activar el milagro {}.').format(isla['wonderName'])
			sendToBot(s, msg)
			return
		else:
			times_activated += 1

		data = rta[2][1]
		for elem in data:
			if 'countdown' in data[elem]:
				enddate     = data[elem]['countdown']['enddate']
				currentdate = data[elem]['countdown']['currentdate']
				wait_time = enddate - currentdate
				break
		else:
			wait_time = 60
