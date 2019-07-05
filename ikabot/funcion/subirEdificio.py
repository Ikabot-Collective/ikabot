#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.web.sesion import normal_get
from ikabot.helpers.process import forkear
from ikabot.helpers.planearViajes import *
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.recursos import getRecursosDisponibles

t = gettext.translation('subirEdificio', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

enviarRecursos = True
subirEdificio = True

def getTiempoDeConstruccion(html, posicion):
	ciudad = getCiudad(html)
	edificio = ciudad['position'][posicion]
	hora_fin = re.search(r'"endUpgradeTime":(\d{10})', html)
	if hora_fin is None:
		msg = _('{}: No espero nada para que {} suba al nivel {:d}').format(ciudad['cityName'], edificio['name'], int(edificio['level']))
		sendToBotDebug(msg, debugON_subirEdificio)
		return 0

	hora_actual = int( time.time() )
	hora_fin    = int( hora_fin.group(1) )
	espera      = hora_fin - hora_actual

	msg = _('{}: Espero {:d} segundos para que {} suba al nivel {:d}').format(ciudad['cityName'], espera, edificio['name'], int(edificio['level']) + 1)
	sendToBotDebug(msg, debugON_subirEdificio)

	return espera + 3

def esperarConstruccion(s, idCiudad, posicion):
	slp = 1
	while slp > 0:
		html = s.get(urlCiudad + idCiudad)
		slp = getTiempoDeConstruccion(html, posicion)
		esperar(slp)
	return getCiudad(html)

def subirEdificio(s, idCiudad, posicion, nivelesASubir, esperarRecursos):

	for lv in range(nivelesASubir):
		ciudad = esperarConstruccion(s, idCiudad, posicion)
		edificio = ciudad['position'][posicion]

		if edificio['canUpgrade'] is False and esperarRecursos:
			while edificio['canUpgrade'] is False:
				time.sleep(60) # tiempo para que se envien los recursos
				segundos = obtenerMinimoTiempoDeEspera(s)
				if segundos == 0:
					break
				else:
					esperar(segundos)
				html = s.get(urlCiudad + idCiudad)
				ciudad = getCiudad(html)
				edificio = ciudad['position'][posicion]

		if edificio['canUpgrade'] is False:
			msg  = _('Ciudad:{}\n').format(ciudad['cityName'])
			msg += _('Edificio:{}\n').format(edificio['name'])
			msg += _('No se pudo terminar de subir el edificio por falta de recursos.\n')
			msg += _('Faltaron subir {:d} niveles').format(nivelesASubir - lv)
			sendToBot(msg)
			return

		for i in range(3):
			url = 'action=CityScreen&function=upgradeBuilding&actionRequest={}&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1'.format(s.token(), idCiudad, posicion, edificio['level'], idCiudad, edificio['building'])
			s.post(url)
			html = s.get(urlCiudad + idCiudad)
			ciudad = getCiudad(html)
			edificio = ciudad['position'][posicion]
			if edificio['isBusy']:
				break

		if edificio['isBusy'] is False:
			msg  = _('El edificio no se amplió\n')
			msg  = _('El edificio {} no se amplió después de tres intentos\n').format(edificio['name'])
			msg += url + '\n'
			msg += str(edificio)
			sendToBot(msg)
			return

def getReductores(ciudad):
	(carpinteria, oficina, prensa, optico, area) = (0, 0, 0, 0, 0)
	for edificio in [ edificio for edificio in ciudad['position'] if edificio['name'] != 'empty' ]:
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

def planearAbastecimiento(s, destino, origenes, faltantes):
	rutas = []
	html = s.get(urlCiudad + destino)
	ciudadD = getCiudad(html)
	for i in range(5):
		faltante = faltantes[i]
		if faltante <= 0:
			continue
		for origen in origenes[i]:
			if faltante == 0:
				break
			html = s.get(urlCiudad + origen)
			ciudadO = getCiudad(html)
			disp = getRecursosDisponibles(html, num=True)[i]
			mandar = disp if disp < faltante else faltante
			faltante -= mandar
			if i == 0:
				ruta = (ciudadO, ciudadD, ciudadD['islandId'], mandar, 0, 0, 0, 0)
			elif i == 1:
				ruta = (ciudadO, ciudadD, ciudadD['islandId'], 0, mandar, 0, 0, 0)
			elif i == 2:
				ruta = (ciudadO, ciudadD, ciudadD['islandId'], 0, 0, mandar, 0, 0)
			elif i == 3:
				ruta = (ciudadO, ciudadD, ciudadD['islandId'], 0, 0, 0, mandar, 0)
			else:
				ruta = (ciudadO, ciudadD, ciudadD['islandId'], 0, 0, 0, 0, mandar)
			rutas.append(ruta)
	planearViajes(s, rutas)

def menuEdificios(s, ids, cities, idCiudad, bienNombre, bienIndex, faltante):
	banner()
	print(_('¿De qué ciudades obtener {}?').format(bienNombre))
	rta = []
	tradegood = [_('V'), 'M', 'C', _('A')]
	maxName = 0
	for name in [ cities[city]['name'] for city in cities if cities[city]['id'] != idCiudad ]:
		if len(name) > maxName:
			maxName = len(name)
	total = 0
	for id in [ id for id in ids if id != idCiudad ]:
		trade = tradegood[ int( cities[id]['tradegood'] ) - 1 ]
		html = s.get(urlCiudad + id)
		ciudad = getCiudad(html)
		disponible = ciudad['recursos'][bienIndex]
		if disponible == 0:
			continue
		opcion = '{}{} ({}): {} [Y/n]:'.format(' ' * (maxName - len(cities[id]['name'])), cities[id]['name'], trade, addPuntos(disponible))
		eleccion = read(msg=opcion, values=['Y', 'y', 'N', 'n', ''])
		if eleccion.lower() == 'n':
			continue
		total += disponible
		rta.append(id)
	if total < faltante:
		global enviarRecursos
		global subirEdificio
		print(_('\nNo hay recursos suficientes.'))
		if enviarRecursos:
			print(_('\n¿Enviar los recursos de todos modos? [Y/n]'))
			choise = read(values=['y', 'Y', 'n', 'N', ''])
			if choise.lower() == 'n':
				enviarRecursos = False
		if subirEdificio:
			print(_('\n¿Intentar aumentar el edificio de todos modos? [y/N]'))
			choise = read(values=['y', 'Y', 'n', 'N', ''])
			if choise.lower() == 'n' or choise == '':
				subirEdificio = False
	return rta

def obtenerLosRecursos(s, idCiudad, posEdificio, niveles, faltante):
	idss, cities = getIdsDeCiudades(s)
	origenes = {}
	for i in range(5):
		if faltante[i] <= 0:
			continue
		bien = tipoDeBien[i]
		ids = menuEdificios(s, idss, cities, idCiudad, bien, i, faltante[i])
		if enviarRecursos is False and subirEdificio:
			print(_('\nSe intentará ampliar el edificio.'))
			enter()
			return
		elif enviarRecursos is False:
			return
		origenes[i] = ids

	if subirEdificio:
		print(_('\nSe enviarán los recursos y se intentará ampliar el edificio.'))
	else:
		print(_('\nSe enviarán los recursos.'))

	enter()

	forkear(s)
	if s.padre is True:
		return True
	else:
		planearAbastecimiento(s, idCiudad, origenes, faltante)
		s.logout()
		exit()

def subirEdificios(s):
	global subirEdificio
	global enviarRecursos
	subirEdificio = True
	enviarRecursos = True

	banner()
	esperarRecursos = False
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
			print(_('\nFalta:'))
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

			print(_('¿Transportar los recursos automáticamente? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				print(_('¿Proceder de todos modos? [Y/n]'))
				rta = read(values=['y', 'Y', 'n', 'N', ''])
				if rta.lower() == 'n':
					return
			else:
				esperarRecursos = True
				faltante = [madera - maderaDisp, vino - vinoDisp, marmol - marmolDisp, cristal - cristalDisp, azufre - azufreDisp]
				obtenerLosRecursos(s, idCiudad, posEdificio, niveles, faltante)
		else:
			print(_('\nTiene materiales suficientes'))
			print(_('¿Proceder? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				return
	except AssertionError:
		pass
	forkear(s)
	if s.padre is True:
		return
	info = _('\nSubir edificio\n')
	info = info + 'Ciudad: {}\nEdificio: {}.Desde {:d}, hasta {:d}'.format(ciudad['cityName'], edificio['name'], desde, hasta)

	setInfoSignal(s, info)
	try:
		if subirEdificio:
			subirEdificio(s, idCiudad, posEdificio, niveles, esperarRecursos)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()
