#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import *
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.recursos import getRecursosDisponibles
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import banner
from ikabot.web.sesion import normal_get

def getTiempoDeConstruccion(html, posicion):
	ciudad = getCiudad(html)
	edificio = ciudad['position'][posicion]
	hora_fin = re.search(r'"endUpgradeTime":(\d{10})', html)
	if hora_fin is None:
		msg = '{}: No espero nada para que {} suba al nivel {:d}'.format(ciudad['cityName'], edificio['name'], int(edificio['level']))
		sendToBotDebug(msg, debugON_subirEdificio)
		return 0

	hora_actual = int( time.time() )
	hora_fin    = int( hora_fin.group(1) )
	espera      = hora_fin - hora_actual

	msg = '{}: Espero {:d} segundos para que {} suba al nivel {:d}'.format(ciudad['cityName'], espera, edificio['name'], int(edificio['level']) + 1)
	sendToBotDebug(msg, debugON_subirEdificio)

	return espera + 3

def esperarConstruccion(s, idCiudad, posicion):
	slp = 1
	while slp > 0:
		html = s.get(urlCiudad + idCiudad)
		slp = getTiempoDeConstruccion(html, posicion)
		esperar(slp)
	return getCiudad(html)

def subirEdificio(s, idCiudad, posicion, nivelesASubir):

	for lv in range(nivelesASubir):
		ciudad = esperarConstruccion(s, idCiudad, posicion)
		edificio = ciudad['position'][posicion]

		if edificio['canUpgrade'] is False:
			msg  = 'No se pudo terminar de subir el edificio por falta de recursos.'
			msg += 'Faltaron subir {:d} niveles'.format(nivelesASubir - lv)
			sendToBot(msg)
			return

		url = 'action=CityScreen&function=upgradeBuilding&actionRequest={}&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1'.format(s.token(), idCiudad, posicion, edificio['level'], idCiudad, edificio['building'])
		s.post(url)

		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		edificio = ciudad['position'][posicion]
		if edificio['isBusy'] is False:
			msg  = 'El edificio no se amplió\n'
			msg += url + '\n'
			msg += str(edificio)
			sendToBot(msg)
			return

def getReductores(ciudad):
	(carpinteria, oficina, prensa, optico, area) = (0, 0, 0, 0, 0)
	for edificio in ciudad['position']:
		if edificio['name'] != 'empty':
			lv = int(edificio['level'])
			if edificio['building'] == 'carpentering':
				carpinteria = lv
			elif edificio['building'] == 'architect':
				oficina = lv
			elif edificio['building'] == 'vineyard':
				prensa = lv
			elif edificio['building'] == 'optician':
				optico = lv
			elif edificio['building'] == 'fireworker':
				area = lv
	return (carpinteria, oficina, prensa, optico, area)

def recursosNecesarios(s, ciudad, edificio, desde, hasta):
	nombre = edificio['building']
	(carpinteria, oficina, prensa, optico, area)  = getReductores(ciudad)
	url = 'http://ycedespacho.hol.es/ikabot.php?edificio={}&desde={}&hasta={}&carpinteria={}&oficina={}&prensa={}&optico={}&area={}'.format(nombre, desde, hasta, carpinteria, oficina, prensa, optico, area)
	rta = normal_get(url).text.split(',')
	return list(map(int, rta))

def subirEdificios(s):
	banner()
	ciudad = elegirCiudad(s)
	idCiudad = ciudad['id']
	edificios = getEdificios(s, idCiudad)
	if edificios == []:
		return
	posEdificio = edificios[0]
	niveles = len(edificios)
	html = s.get(urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	edificio = ciudad['position'][posEdificio]
	desde = int(edificio['level'])
	if edificio['isBusy']:
		desde += 1
	hasta = desde + niveles
	try:
		(madera, vino, marmol, cristal, azufre) = recursosNecesarios(s, ciudad, edificio, desde, hasta)
		assert madera != 0
		html = s.get(urlCiudad + idCiudad)
		(maderaDisp, vinoDisp, marmolDisp, cristalDisp, azufreDisp) = getRecursosDisponibles(html, num=True)
		if maderaDisp < madera or vinoDisp < vino or marmolDisp < marmol or cristalDisp < cristal or azufreDisp < azufre:
			print('\nFalta:')
			if maderaDisp < madera:
				print('{} de madera'.format(addPuntos(madera - maderaDisp)))
			if vinoDisp < vino:
				print('{} de vino'.format(addPuntos(vino - vinoDisp)))
			if marmolDisp < marmol:
				print('{} de marmol'.format(addPuntos(marmol - marmolDisp)))
			if cristalDisp < cristal:
				print('{} de cristal'.format(addPuntos(cristal - cristalDisp)))
			if azufreDisp < azufre:
				print('{} de azufre'.format(addPuntos(azufre - azufreDisp)))
			print('¿Proceder de todos modos? [Y/n]')
			rta = read()
			if rta.lower() == 'n':
				return
		else:
			print('\nTiene materiales suficientes')
			print('¿Proceder? [Y/n]')
			rta = read()
			if rta.lower() == 'n':
				return
	except AssertionError:
		pass
	forkear(s)
	if s.padre is True:
		return

	info = '\nSubir edificio\n'
	info = info + 'Ciudad: {}\nEdificio: {}.Desde {:d}, hasta {:d}'.format(ciudad['cityName'], edificio['name'], desde, hasta)

	setInfoSignal(s, info)
	try:
		subirEdificio(s, idCiudad, posEdificio, niveles)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()
