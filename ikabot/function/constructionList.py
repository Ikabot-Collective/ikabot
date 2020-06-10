#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import json
import math
import random
import gettext
import traceback
import threading
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.web.sesion import normal_get
from ikabot.helpers.planearViajes import *
from ikabot.helpers.getJson import getCity
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

def getConstructionTime(s, html, position):
	city = getCity(html)
	building = city['position'][position]
	final_time = re.search(r'"endUpgradeTime":(\d{10})', html)
	if final_time is None:
		msg = _('{}: I don\'t wait anything so that {} gets to the level {:d}').format(city['cityName'], building['name'], building['level'])
		sendToBotDebug(s, msg, debugON_constructionList)
		return 0

	current_time    = int( time.time() )
	final_time      = int( final_time.group(1) )
	seconds_to_wait = final_time - current_time
	if seconds_to_wait <= 0:
		seconds_to_wait = 0

	msg = _('{}: I wait {:d} seconds so that {} gets to the level {:d}').format(city['cityName'], seconds_to_wait, building['name'], building['level'] + 1)
	sendToBotDebug(s, msg, debugON_constructionList)

	return seconds_to_wait

def waitForConstruction(s, cityId, position):
	slp = 1
	while slp > 0:
		html = s.get(urlCiudad + cityId)
		slp = getConstructionTime(s, html, position)
		wait(slp + 5)
	html = s.get(urlCiudad + cityId)
	city = getCity(html)
	building = city['position'][position]
	msg = _('{}: The building {} reached the level {:d}.').format(city['cityName'], building['name'], building['level'])
	sendToBotDebug(s, msg, debugON_constructionList)
	return city

def expandBuilding(s, cityId, building, waitForResources):
	current_level = building['level']
	if building['isBusy']:
		current_level += 1
	levels_to_upgrade = building['upgradeTo'] - current_level
	position = building['position']

	time.sleep(random.randint(5,15)) # to avoid race conditions with sendResourcesNeeded

	for lv in range(levels_to_upgrade):
		city = waitForConstruction(s, cityId, position)
		building = city['position'][position]

		if building['canUpgrade'] is False and waitForResources is True:
			while building['canUpgrade'] is False:
				time.sleep(60)
				seconds = getMinimumWaitingTime(s)
				html = s.get(urlCiudad + cityId)
				city = getCity(html)
				building = city['position'][position]
				# if no ships are comming, exit no matter if the building can or can't upgrade
				if seconds == 0:
					break
				wait(seconds + 5)

		if building['canUpgrade'] is False:
			msg  = _('City:{}\n').format(city['cityName'])
			msg += _('Building:{}\n').format(building['name'])
			msg += _('The building could not be completed due to lack of resources.\n')
			msg += _('Missed {:d} levels').format(levels_to_upgrade - lv)
			sendToBot(s, msg)
			return

		url = 'action=CityScreen&function=upgradeBuilding&actionRequest=REQUESTID&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1'.format(cityId, position, building['level'], cityId, building['building'])
		resp = s.post(url)
		html = s.get(urlCiudad + cityId)
		city = getCity(html)
		building = city['position'][position]
		if building['isBusy'] is False:
			msg  = _('{}: The building {} was not extended').format(city['cityName'], building['name'])
			sendToBot(s, msg)
			sendToBot(s, resp)
			return

		msg = _('{}: The building {} is being extended to level {:d}.').format(city['cityName'], building['name'], building['level']+1)
		sendToBotDebug(s, msg, debugON_constructionList)

	msg = _('{}: The building {} finished extending to level: {:d}.').format(city['cityName'], building['name'], building['level']+1)
	sendToBotDebug(s, msg, debugON_constructionList)

def getReductores(city):
	reductores = [0] * len(materials_names)
	assert len(reductores) == 5

	for building in city['position']:
		if building['name'] == 'empty':
			continue
		lv = building['level']
		if building['building'] == 'carpentering':
			reductores[0] = lv
		elif building['building'] == 'vineyard':
			reductores[1] = lv
		elif building['building'] == 'architect':
			reductores[2] = lv
		elif building['building'] == 'optician':
			reductores[3] = lv
		elif building['building'] == 'fireworker':
			reductores[4] = lv
	return reductores

def getResourcesNeeded(s, city, building, current_level, final_level):
	# get html with information about buildings
	url = 'view=buildingDetail&buildingId=0&helpId=1&backgroundView=city&currentCityId={}&templateView=ikipedia&actionRequest=REQUESTID&ajax=1'.format(city['id'])
	rta = s.post(url)
	rta = json.loads(rta, strict=False)
	html = rta[1][1][1]

	# get html with information about buildings costs
	regex = r'<div class="(?:selected)? button_building '+ re.escape(building['building']) + r'"\s*onmouseover="\$\(this\)\.addClass\(\'hover\'\);" onmouseout="\$\(this\)\.removeClass\(\'hover\'\);"\s*onclick="ajaxHandlerCall\(\'\?(.*?)\'\);'
	match = re.search(regex, html)
	url = match.group(1)
	url += 'backgroundView=city&currentCityId={}&templateView=buildingDetail&actionRequest=REQUESTID&ajax=1'.format(city['id'])
	rta = s.post(url)
	rta = json.loads(rta, strict=False)
	html_costs = rta[1][1][1]

	# if the user has all the resource saving studies, we save that in the session data (one less request)
	sessionData = s.getSessionData()
	if 'reduccion_inv_max' in sessionData:
		reduccion_inv = 14
	else:
		# get the studies
		url = 'view=noViewChange&researchType=economy&backgroundView=city&currentCityId={}&templateView=researchAdvisor&actionRequest=REQUESTID&ajax=1'.format(city['id'])
		rta = s.post(url)
		rta = json.loads(rta, strict=False)
		studies = rta[2][1]['new_js_params']
		studies = json.loads(studies, strict=False)
		studies = studies['currResearchType']

		# look for resource saving studies
		reduccion_inv = 0
		for study in studies:
			if studies[study]['liClass'] != 'explored':
				continue
			link = studies[study]['aHref']
			if '2020' in link:
				reduccion_inv += 2
			elif '2060' in link:
				reduccion_inv += 4
			elif '2100' in link:
				reduccion_inv += 8

		# if the user has all the resource saving studies, save that in the session data
		if reduccion_inv == 14:
			sessionData['reduccion_inv_max'] = True
			s.setSessionData(sessionData)

	# calculate cost reductions
	reduccion_inv /= 100
	reduccion_inv = 1 - reduccion_inv

	# get buildings that reduce the cost of upgrades
	reductores = getReductores(city)

	# get the type of resources that this upgrade will cost (wood, marble, etc)
	resources_types = re.findall(r'<th class="costs"><img src="skin/resources/icon_(.*?)\.png"/></th>', html_costs)[:-1]

	# get the actual cost of each upgrade
	matches = re.findall(r'<td class="level">\d+</td>(?:\s+<td class="costs">.*?</td>)+', html_costs)

	# calculate the cost of the entire upgrade, taking into account all the possible reductions
	final_costs = [0] * len(materials_names)
	levels_to_upgrade = 0
	for match in matches:
		lv = re.search(r'"level">(\d+)</td>', match).group(1)
		lv = int(lv)

		if lv <= current_level:
			continue
		if lv > final_level:
			break

		levels_to_upgrade += 1

		# get the costs for the current level
		costs = re.findall(r'<td class="costs">([\d,\.]*)</td>', match)
		for i in range(len(costs)):
			resource_type = resources_types[i]
			for j in range(len(materials_names_tec)):
				name = materials_names_tec[j]
				if resource_type == name:
					index = j
					break

			# get the cost of the current resource type
			cost = costs[i]
			cost = cost.replace(',', '').replace('.', '')
			cost = 0 if cost == '' else int(cost)

			# calculate all the reductions
			real_cost = Decimal(cost)
			# investigation reduction
			original_cost = Decimal(real_cost) / Decimal(reduccion_inv)
			# special building reduction
			real_cost -= Decimal(original_cost) * (Decimal(reductores[index]) / Decimal(100))

			final_costs[index] += math.ceil(real_cost)

	if levels_to_upgrade < final_level - current_level:
		print(_('This building only allows you to expand {:d} more levels').format(levels_to_upgrade))
		msg = _('Expand {:d} levels? [Y/n]:').format(levels_to_upgrade)
		rta = read(msg=msg, values=['Y', 'y', 'N', 'n', ''])
		if rta.lower() == 'n':
			return [-1,-1,-1,-1,-1]

	return final_costs

def sendResourcesNeeded(s, idDestiny, origins, missingArr):
	#set_child_mode(s)

	info = _('\nTransport resources to upload building\n')

	try:
		routes = []
		html = s.get(urlCiudad + idDestiny)
		cityD = getCity(html)
		for i in range(len(materials_names)):
			missing = missingArr[i]
			if missing <= 0:
				continue

			# send the resources from each origin city
			for cityO in origins[i]:
				if missing == 0:
					break

				available = cityO['recursos'][i]
				send = min(available, missing)
				missing -= send
				toSend = [0] * len(materials_names)
				toSend[i] = send
				route = (cityO, cityD, cityD['islandId'], *toSend)
				routes.append(route)
		executeRoutes(s, routes)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
		# no s.logout() because this is a thread, not a process

def chooseResourceProviders(s, ids, cities, idCiudad, resource, missing):
	global sendResources
	sendResources = True
	global expand
	expand = True

	banner()
	print(_('From what cities obtain {}?').format(materials_names[resource].lower()))

	tradegood_initials = [ material_name[0] for material_name in materials_names ]
	maxName = max ( [ len(cities[city]['name']) for city in cities if cities[city]['id'] != idCiudad ] )

	origin_cities = []
	total_available = 0
	for cityId in ids:
		if cityId == idCiudad:
			continue

		html = s.get(urlCiudad + cityId)
		city = getCity(html)

		available = city['recursos'][resource]
		if available == 0:
			continue

		# ask the user it this city should provide resources
		tradegood_initial = tradegood_initials[ int( cities[cityId]['tradegood'] ) ]		
		pad = ' ' * (maxName - len(cities[cityId]['name']))
		msg = '{}{} ({}): {} [Y/n]:'.format(pad, cities[cityId]['name'], tradegood_initial, addDot(available))
		eleccion = read(msg=msg, values=['Y', 'y', 'N', 'n', ''])
		if eleccion.lower() == 'n':
			continue

		# if so, save the city and calculate the total amount resources to send
		total_available += available
		origin_cities.append(city)
		# if we have enough resources, return
		if total_available >= missing:
			return origin_cities

	# if we reach this part, there are not enough resources to expand the building
	print(_('\nThere are not enough resources.'))

	if len(origin_cities) > 0:
		print(_('\nSend the resources anyway? [Y/n]'))
		choise = read(values=['y', 'Y', 'n', 'N', ''])
		if choise.lower() == 'n':
			sendResources = False

	print(_('\nTry to expand the building anyway? [y/N]'))
	choise = read(values=['y', 'Y', 'n', 'N', ''])
	if choise.lower() == 'n' or choise == '':
		expand = False

	return origin_cities

def sendResourcesMenu(s, idCiudad, missing):
	cities_ids, cities = getIdsOfCities(s)
	origins = {}
	# for each missing resource, choose providers
	for resource in range(len(missing)):
		if missing[resource] <= 0:
			continue

		origin_cities = chooseResourceProviders(s, cities_ids, cities, idCiudad, resource, missing[resource])
		if sendResources is False and expand:
			print(_('\nThe building will be expanded if possible.'))
			enter()
			return
		elif sendResources is False:
			return
		origins[resource] = origin_cities

	if expand:
		print(_('\nThe resources will be sent and the building will be expanded if possible.'))
	else:
		print(_('\nThe resources will be sent.'))

	enter()

	# create a new thread to send the resources
	t = threading.Thread(target=sendResourcesNeeded, args=(s, idCiudad, origins, missing,))
	t.start()

def getBuildingToExpand(s, cityId):
	html = s.get(urlCiudad + cityId)
	city = getCity(html)

	banner()
	# show the buildings available to expand (ignore empty spaces)
	print(_('Which building do you want to expand?\n'))
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
			level = level + '+'
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
		print(_('In which city do you want to expand a building?'))
		city = chooseCity(s)
		cityId = city['id']
		building = getBuildingToExpand(s, cityId)
		if building is None:
			e.set()
			return

		current_level = building['level']
		if building['isBusy']:
			current_level += 1
		final_level = building['upgradeTo']

		# calculate the resources that are needed
		resourcesNeeded = getResourcesNeeded(s, city, building, current_level, final_level)
		if -1 in resourcesNeeded:
			e.set()
			return

		# calculate the resources that are missing
		missing = [0] * len(materials_names)
		for i in range(len(materials_names)):
			if city['recursos'][i] < resourcesNeeded[i]:
				missing[i] = resourcesNeeded[i] - city['recursos'][i]

		# show missing resources to the user
		if sum(missing) > 0:
			print(_('\nMissing:'))
			for i in range(len(materials_names)):
				if missing[i] == 0:
					continue
				name = materials_names[i].lower()
				print(_('{} of {}').format(addDot(missing[i]), name))
			print('')

			# if the user wants, send the resources from the selected cities
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
				sendResourcesMenu(s, cityId, missing)
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
	info = info + _('City: {}\nBuilding: {}. From {:d}, to {:d}').format(city['cityName'], building['name'], current_level, final_level)

	setInfoSignal(s, info)
	try:
		if expand:
			expandBuilding(s, cityId, building, wait_resources)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()
