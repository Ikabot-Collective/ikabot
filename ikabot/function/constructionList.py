#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import json
import math
import gettext
import traceback
import multiprocessing
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.web.sesion import normal_get
from ikabot.helpers.planearViajes import *
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.recursos import getRecursosDisponibles
t = gettext.translation('constructionList', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

sendResources = True
expand = True

def getTiempoDeConstruccion(s, html, posicion):
	ciudad = getCiudad(html)
	edificio = ciudad['position'][posicion]
	hora_fin = re.search(r'"endUpgradeTime":(\d{10})', html)
	if hora_fin is None:
		msg = _('{}: I don\'t wait anything so that {} gets to the level {:d}').format(ciudad['cityName'], edificio['name'], edificio['level'])
		sendToBotDebug(s, msg, debugON_constructionList)
		return 0

	hora_actual = int( time.time() )
	hora_fin    = int( hora_fin.group(1) )
	espera      = hora_fin - hora_actual
	if espera <= 0:
		espera = 0

	msg = _('{}: I wait {:d} seconds so that {} gets to the level {:d}').format(ciudad['cityName'], espera, edificio['name'], edificio['level'] + 1)
	sendToBotDebug(s, msg, debugON_constructionList)

	return espera

def esperarConstruccion(s, idCiudad, posicion):
	slp = 1
	while slp > 0:
		html = s.get(urlCiudad + idCiudad)
		slp = getTiempoDeConstruccion(s, html, posicion)
		wait(slp + 5)
	html = s.get(urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	edificio = ciudad['position'][posicion]
	msg = _('{}: The building {} reached the level {:d}.').format(ciudad['cityName'], edificio['name'], edificio['level'])
	sendToBotDebug(s, msg, debugON_constructionList)
	return ciudad

def constructionList1(s, idCiudad, building, esperarRecursos):
	current_level = building['level']
	if building['isBusy']:
		current_level += 1
	nivelesASubir = building['upgradeTo'] - current_level
	posicion = building['position']

	for lv in range(nivelesASubir):
		ciudad = esperarConstruccion(s, idCiudad, posicion)
		edificio = ciudad['position'][posicion]

		if edificio['canUpgrade'] is False and esperarRecursos is True:
			while edificio['canUpgrade'] is False:
				time.sleep(60) # tiempo para que se envien los recursos
				segundos = getMinimumWaitingTime(s)
				html = s.get(urlCiudad + idCiudad)
				ciudad = getCiudad(html)
				edificio = ciudad['position'][posicion]
				if segundos == 0:
					break
				wait(segundos)

		if edificio['canUpgrade'] is False:
			msg  = _('City:{}\n').format(ciudad['cityName'])
			msg += _('Building:{}\n').format(edificio['name'])
			msg += _('The building could not be completed due to lack of resources.\n')
			msg += _('Missed {:d} levels').format(nivelesASubir - lv)
			sendToBot(s, msg)
			return

		for i in range(3):
			url = 'action=CityScreen&function=upgradeBuilding&actionRequest={}&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1'.format(s.token(), idCiudad, posicion, edificio['level'], idCiudad, edificio['building'])
			s.post(url)
			html = s.get(urlCiudad + idCiudad)
			ciudad = getCiudad(html)
			edificio = ciudad['position'][posicion]
			if edificio['isBusy']:
				break
		else:
			msg  = _('{}: The building {} was not extended after three tries\n').format(ciudad['cityName'], edificio['name'])
			sendToBot(s, msg)
			return

		msg = _('{}: The building {} is being extended to level {:d}.').format(ciudad['cityName'], edificio['name'], edificio['level']+1)
		sendToBotDebug(s, msg, debugON_constructionList)

	msg = _('{}: The building {} finished extending to level: {:d}.').format(ciudad['cityName'], edificio['name'], edificio['level']+1)
	sendToBotDebug(s, msg, debugON_constructionList)

def getReductores(ciudad):
	(carpinteria, oficina, prensa, optico, area) = (0, 0, 0, 0, 0)
	for edificio in [ edificio for edificio in ciudad['position'] if edificio['name'] != 'empty' ]:
		lv = edificio['level']
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

def getResourcesNeeded(s, ciudad, edificio, desde, hasta):
	url = 'view=buildingDetail&buildingId=0&helpId=1&backgroundView=city&currentCityId={}&templateView=ikipedia&actionRequest={}&ajax=1'.format(ciudad['id'], s.token())
	rta = s.post(url)
	rta = json.loads(rta, strict=False)
	html = rta[1][1][1]

	regex = r'<div class="(?:selected)? button_building '+ re.escape(edificio['building']) + r'"\s*onmouseover="\$\(this\)\.addClass\(\'hover\'\);" onmouseout="\$\(this\)\.removeClass\(\'hover\'\);"\s*onclick="ajaxHandlerCall\(\'\?(.*?)\'\);'
	match = re.search(regex, html)
	url = match.group(1)
	url += 'backgroundView=city&currentCityId={}&templateView=buildingDetail&actionRequest={}&ajax=1'.format(ciudad['id'], s.token())
	rta = s.post(url)
	rta = json.loads(rta, strict=False)
	html_costos = rta[1][1][1]

	sessionData = s.getSessionData()
	if 'reduccion_inv_max' in sessionData:
		reduccion_inv = 14
	else:
		url = 'view=noViewChange&researchType=economy&backgroundView=city&currentCityId={}&templateView=researchAdvisor&actionRequest={}&ajax=1'.format(ciudad['id'], s.token())
		rta = s.post(url)
		rta = json.loads(rta, strict=False)
		studies = rta[2][1]['new_js_params']
		studies = json.loads(studies, strict=False)
		studies = studies['currResearchType']

		reduccion_inv = 0
		for study in studies:
			link = studies[study]['aHref']
			isExplored = studies[study]['liClass'] == 'explored'

			if '2020' in link and isExplored:
				reduccion_inv += 2
			elif '2060' in link and isExplored:
				reduccion_inv += 4
			elif '2100' in link and isExplored:
				reduccion_inv += 8

		if reduccion_inv == 14:
			sessionData['reduccion_inv_max'] = True
			s.setSessionData(sessionData)

	reduccion_inv /= 100
	reduccion_inv = 1 - reduccion_inv

	reductores = getReductores(ciudad)

	recursos_tipo = re.findall(r'<th class="costs"><img src="skin/resources/icon_(.*?)\.png"/></th>', html_costos)[:-1]
	recurso_index = {'wood': 0, 'wine': 1, 'marble': 2, 'glass': 3, 'sulfur': 4}

	matches = re.findall(r'<td class="level">\d+</td>(?:\s+<td class="costs">.*?</td>)+', html_costos)

	costos = [0,0,0,0,0]
	niveles_a_subir = 0
	for match in matches:
		lv = re.search(r'"level">(\d+)</td>', match).group(1)
		lv = int(lv)

		if lv <= desde:
			continue
		if lv > hasta:
			break

		niveles_a_subir += 1

		costs = re.findall(r'<td class="costs">([\d,\.]*)</td>', match)
		for i in range(len(costs)):
			recurso = recursos_tipo[i]
			index = recurso_index[recurso]

			costo = costs[i]
			costo = costo.replace(',', '').replace('.', '')
			costo = 0 if costo == '' else int(costo)

			costo_real = Decimal(costo)
			costo_original = Decimal(costo_real) / Decimal(reduccion_inv)
			costo_real -= Decimal(costo_original) * (Decimal(reductores[index]) / Decimal(100))

			costos[index] += math.ceil(costo_real)

	if niveles_a_subir < hasta - desde:
		print(_('This building only allows you to expand {:d} more levels').format(niveles_a_subir))
		msg = _('Expand {:d} levels? [Y/n]:').format(niveles_a_subir)
		eleccion = read(msg=msg, values=['Y', 'y', 'N', 'n', ''])
		if eleccion.lower() == 'n':
			return [-1,-1,-1,-1,-1]

	return costos

def planearAbastecimiento(s, destino, origenes, faltantes):
	set_child_mode(s)

	info = _('\nTransport resources to upload building\n')
	setInfoSignal(s, info)

	try:
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
				disp = ciudadO['recursos'][i]
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
		executeRoutes(s, rutas)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def menuEdificios(s, ids, cities, idCiudad, bienNombre, bienIndex, faltante):
	banner()
	print(_('From what cities obtain {}?').format(bienNombre))
	rta = []
	tradegood = [_('W'), _('M'), _('C'), _('S')]
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
		opcion = '{}{} ({}): {} [Y/n]:'.format(' ' * (maxName - len(cities[id]['name'])), cities[id]['name'], trade, addDot(disponible))
		eleccion = read(msg=opcion, values=['Y', 'y', 'N', 'n', ''])
		if eleccion.lower() == 'n':
			continue
		total += disponible
		rta.append(id)
		if total >= faltante:
			return rta
	if total < faltante:
		global sendResources
		global expand
		print(_('\nThere are not enough resources.'))
		if sendResources:
			print(_('\nSend the resources anyway? [Y/n]'))
			choise = read(values=['y', 'Y', 'n', 'N', ''])
			if choise.lower() == 'n':
				sendResources = False
		if expand:
			print(_('\nTry to expand the building anyway? [y/N]'))
			choise = read(values=['y', 'Y', 'n', 'N', ''])
			if choise.lower() == 'n' or choise == '':
				expand = False
	return rta

def obtenerLosRecursos(s, idCiudad, posEdificio, niveles, faltante):
	idss, cities = getIdsOfCities(s)
	origenes = {}
	for i in range(5):
		if faltante[i] <= 0:
			continue
		bien = materials_names[i]
		ids = menuEdificios(s, idss, cities, idCiudad, bien, i, faltante[i])
		if sendResources is False and expand:
			print(_('\nThe building will be expanded if possible.'))
			enter()
			return
		elif sendResources is False:
			return
		origenes[i] = ids

	if expand:
		print(_('\nThe resources will be sent and the building will be expanded if possible.'))
	else:
		print(_('\nThe resources will be sent.'))

	enter()

	multiprocessing.Process(target=planearAbastecimiento, args=(s, idCiudad, origenes, faltante)).start()

def getBuildingToExpand(s, cityId):
	html = s.get(urlCiudad + cityId)
	city = getCiudad(html)

	banner()
	print(_('(0)\t\texit'))
	buildings = [ building for building in city['position'] if building['name'] != 'empty' ]
	for i in range(len(buildings)):
		building = buildings[i]

		level = building['level']
		if level < 10:
			level = ' ' + str(level)
		else:
			level = str(level)
		if building['isBusy']:
			level + '+'
		print(_('({:d})\tlv:{}\t{}').format(i+1, level, building['name']))

	choise = read(min=0, max=len(buildings))
	if choise == 0:
		return None

	building = buildings[choise - 1]

	current_level = int(building['level'])
	# if the building is being expanded, add 1 level
	if building['isBusy']:
		current_level += 1

	banner()
	print(_('building:{}').format(building['name']))
	print(_('current level:{}').format(current_level))

	final_level = read(min=current_level, msg=_('increase to level:'))
	building['upgradeTo'] = final_level

	return building

def constructionList(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		global expand
		global sendResources
		expand = True
		sendResources = True

		banner()
		wait_resources = False
		city = chooseCity(s)
		idCiudad = city['id']
		building = getBuildingToExpand(s, idCiudad)
		if building is None:
			e.set()
			return

		building_pos = building['position']
		current_level = building['level']
		if building['isBusy']:
			current_level += 1
		final_level = building['upgradeTo']
		niveles = final_level - current_level

		html = s.get(urlCiudad + idCiudad)
		city = getCiudad(html)
		edificio = city['position'][building_pos]

		resourcesNeeded = getResourcesNeeded(s, city, edificio, current_level, final_level)
		if resourcesNeeded[0] == -1:
			e.set()
			return

		missing = [0] * len(materials_names)

		for i in range(len(materials_names)):
			if city['recursos'][i] < resourcesNeeded[i]:
				missing[i] = resourcesNeeded[i] - city['recursos'][i]

		if sum(missing) > 0:
			print(_('\nMissing:'))
			for i in range(len(materials_names)):
				name = materials_names[i].lower()
				print(_('{} of {}').format(addDot(missing[i]), name))

			print(_('Automatically transport resources? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				print(_('Proceed anyway? [Y/n]'))
				rta = read(values=['y', 'Y', 'n', 'N', ''])
				if rta.lower() == 'n':
					e.set()
					return
			else:
				wait_resources = True
				obtenerLosRecursos(s, idCiudad, building_pos, niveles, missing)
		else:
			print(_('\nYou have enough materials'))
			print(_('Proceed? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				e.set()
				return
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nUpgrade building\n')
	info = info + _('City: {}\nBuilding: {}. From {:d}, to {:d}').format(city['cityName'], edificio['name'], current_level, final_level)

	setInfoSignal(s, info)
	try:
		if expand:
			constructionList1(s, idCiudad, building, wait_resources)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()
