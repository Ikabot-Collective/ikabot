#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.recursos import getRecursosDisponibles
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import banner
from ikabot.web.sesion import normal_get

def getTiempoDeConstruccion(html):
	fin = re.search(r'"endUpgradeTime":(\d{10})', html)
	if fin is None:
		return 0
	inicio = re.search(r'serverTime:\s"(\d{10})', html)
	espera = int(fin.group(1)) - int(inicio.group(1))
	if espera < 0:
		espera = 5
	return espera

def esperarConstruccion(s, idCiudad):
	slp = 1
	while slp > 0:
		html = s.get(urlCiudad + idCiudad)
		slp = getTiempoDeConstruccion(html)
		time.sleep(slp + 5)
	return getCiudad(html)

def subirEdificio(s, idCiudad, posicion):
	ciudad = esperarConstruccion(s, idCiudad)
	edificio = ciudad['position'][posicion]

	if edificio['canUpgrade'] is False:
		msg = 'No se pudo terminar de subir el edificio por falta de recursos.'
		raise Exception(msg)

	url = 'action=CityScreen&function=upgradeBuilding&actionRequest={}&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1'.format(s.token(), idCiudad, posicion, edificio['level'], idCiudad, edificio['building'])
	s.post(url)

	html = s.get(urlCiudad + idCiudad)
	fin = re.search(r'"endUpgradeTime":(\d{10})', html)
	if fin is None:
		msg  = 'El edificio no se amplió\n'
		msg += url + '\n'
		msg += str(edificio)
		raise Exception(msg)
	inicio = re.search(r'serverTime:\s"(\d{10})', html)
	espera = int(fin.group(1)) - int(inicio.group(1))
	msg = ciudad['cityName'] + ': '
	if espera > 0:
		msg += 'Espero {:d} segundos para subir {} del lv {} al siguiente'.format(espera, edificio['name'], edificio['level'])
		sendToBot(s, msg)
	elif espera == 0:
		msg += 'Espero ¡0! segundos para subir {} del lv {} al siguiente'.format(edificio['name'], edificio['level'])
		sendToBot(s, msg)
	else:
		msg += 'Espera negativa de {:d} segundos para subir {} del lv {} al siguiente'.format(espera*-1, edificio['name'], edificio['level'])
		fd = open('negativeWaitError', 'a')
		fd.write(msg + '\n'*2 + html + '*'*20  + '\n'*5)
		fd.close()
		raise Exception(msg)

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

def recursosNecesarios(s, idCiudad, posEdifiico,  niveles):
	html = s.get(urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	edificio = ciudad['position'][posEdifiico]
	desde = int(edificio['level'])
	if edificio['isBusy']:
		desde += 1
	hasta = desde + niveles
	nombre = ciudad['position'][posEdifiico]['building']
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
	try:
		(madera, vino, marmol, cristal, azufre) = recursosNecesarios(s, idCiudad, edificios[0], len(edificios))
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
	info = info + 'Ciudad: {}\nEdificio: {}'.format(ciudad['cityName'], ciudad['position'][edificios[0]]['name'])

	setInfoSignal(s, info)
	try:
		for edificio in edificios:
			subirEdificio(s, idCiudad, edificio)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()
