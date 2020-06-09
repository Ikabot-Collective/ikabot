#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCity
from ikabot.helpers.planearViajes import executeRoutes
from ikabot.helpers.recursos import *
from ikabot.helpers.varios import addDot
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.gui import banner

t = gettext.translation('distributeResources',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def distributeResources(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		print(_('What resource do you want to distribute?'))
		print(_('(0) Exit'))
		for i in range(len(materials_names)):
			print('({:d}) {}'.format(i+1, materials_names[i]))
		resource = read(min=0, max=5)
		if resource == 0:
			e.set() #give main process control before exiting
			return
		resource -= 1

		if resource == 0:
			evenly = True
		else:
			print('\nDistributes resources from cities that do produce them \nto cities that do not (1) or distribute them evenly among all cities (2)?')
			type_distribution = read(min=1, max=2)
			evenly = type_distribution == 2

		if evenly:
			routes = distribute_evenly(s, resource)
		else:
			routes = distribute_unevenly(s, resource)

		if routes is None:
			e.set()
			return

		banner()
		print(_('\nThe following shipments will be made:\n'))
		for route in routes:
			print('{} -> {} : {} {}'.format(route[0]['name'], route[1]['name'], route[resource+3], materials_names[resource])) #displays all routes to be executed in console

		print(_('\nProceed? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			e.set()
			return

	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set() #this is where we give back control to main process

	info = _('\nDistribute {}\n').format(materials_names[resource])
	setInfoSignal(s, info)

	try:
		executeRoutes(s, routes) #plan trips for all the routes
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg) #sends message to telegram bot
	finally:
		s.logout()

def distribute_evenly(s, resource):
	resourceTotal = 0
	(cityIDs, cities) = getIdsOfCities(s)

	originCities = {}
	destinationCities = {}
	allCities = {}
	for cityID in cityIDs:

		html = s.get(urlCiudad + cityID) #load html from the get request for that particular city
		city = getCity(html) #convert the html to a city object

		resourceTotal += city['recursos'][resource] #the cities resources are added to the total
		allCities[cityID] = city #adds the city to all cities


	# if a city doesn't have enough storage to fit resourceAverage
	# ikabot will send enough resources to fill the store to the max
	# then, resourceAverage will be recalculated
	resourceAverage = resourceTotal // len(allCities)
	while True:

		len_prev = len(destinationCities)
		for cityID in allCities:
			if cityID in destinationCities:
				continue
			freeStorage = allCities[cityID]['freeSpaceForResources'][resource]
			storage = allCities[cityID]['storageCapacity']
			if storage < resourceAverage:
				destinationCities[cityID] = freeStorage
				resourceTotal -= storage

		resourceAverage = resourceTotal // ( len(allCities) - len(destinationCities) )

		if len_prev == len(destinationCities):
			for cityID in allCities:
				if cityID in destinationCities:
					continue
				if allCities[cityID]['recursos'][resource] > resourceAverage:
					originCities[cityID] = allCities[cityID]['recursos'][resource] - resourceAverage
				else:
					destinationCities[cityID] = resourceAverage - allCities[cityID]['recursos'][resource]
			break

	originCities = {k: v for k, v in sorted(originCities.items(), key=lambda item: item[1],reverse=True)} #sort origin cities in descending order
	destinationCities = {k: v for k, v in sorted(destinationCities.items(), key=lambda item: item[1])}    #sort destination cities in ascending order

	routes = []

	for originCityID in originCities: #iterate through all origin city ids

		for destinationCityID in destinationCities: #iterate through all destination city ids
			if originCities[originCityID] == 0 or destinationCities[destinationCityID] == 0:
				continue

			if originCities[originCityID] > destinationCities[destinationCityID]: #if there's more resources above average in the origin city than resources below average in the destination city (origin city needs to have a surplus and destination city needs to have a deficit of resources for a route to be considered)
				toSend = destinationCities[destinationCityID] #number of resources to send is the number of resources below average in destination city
			else:
				toSend = originCities[originCityID] #send the amount of resources above average of the current origin city

			if toSend == 0:
				continue

			toSendArr = [0] * len(materials_names)
			toSendArr[resource] = toSend
			route = (allCities[originCityID], allCities[destinationCityID], allCities[destinationCityID]['islandId'], *toSendArr)
			routes.append(route)

			# ROUTE BLOCK
			if originCities[originCityID] > destinationCities[destinationCityID]:
				originCities[originCityID] -= destinationCities[destinationCityID] #remove the sent amount from the origin city's surplus
				destinationCities[destinationCityID] = 0 #set the amount of resources below average in destination city to 0
			else:
				destinationCities[destinationCityID] -= originCities[originCityID] #remove the sent amount from the amount of resources below average in current destination city
				originCities[originCityID] = 0 #set the amount of resources above average in origin city to 0

	return routes

def distribute_unevenly(s, recurso):

	recursoTotal = 0
	(idsCiudades, ciudades) = getIdsOfCities(s)
	ciudadesOrigen = {}
	ciudadesDestino = {}
	for idCiudad in idsCiudades:
		esTarget =  ciudades[idCiudad]['tradegood'] == str(recurso)
		if esTarget:
			html = s.get(urlCiudad + idCiudad)
			ciudad = getCity(html)
			if recurso == 1:
				ciudad['disponible'] = ciudad['recursos'][recurso] - ciudad['consumo'] - 1
			else:
				ciudad['disponible'] = ciudad['recursos'][recurso]
			if ciudad['disponible'] < 0:
				ciudad['disponible'] = 0
			recursoTotal += ciudad['disponible']
			ciudadesOrigen[idCiudad] = ciudad
		else:
			html = s.get(urlCiudad + idCiudad)
			ciudad = getCity(html)
			ciudad['disponible'] = ciudad['freeSpaceForResources'][recurso]
			if ciudad['disponible'] > 0:
				ciudadesDestino[idCiudad] = ciudad

	if recursoTotal <= 0:
		print(_('\nThere are no resources to send.'))
		enter()
		return None
	if len(ciudadesDestino) == 0:
		print(_('\nThere is no space available to send resources.'))
		enter()
		return None

	recursoXciudad = recursoTotal // len(ciudadesDestino)
	espacios_disponibles = [ ciudadesDestino[city]['disponible'] for city in ciudadesDestino ]
	totalEspacioDisponible = sum( espacios_disponibles )
	restanteAEnviar = min(recursoTotal, totalEspacioDisponible)
	toSend = {}

	while restanteAEnviar > 0:
		len_prev = len(toSend)
		for city in ciudadesDestino:
			ciudad = ciudadesDestino[city]
			if city not in toSend and ciudad['disponible'] < recursoXciudad:
				toSend[city] = ciudad['disponible']
				restanteAEnviar -= ciudad['disponible']

		if len(toSend) == len_prev:
			for city in ciudadesDestino:
				if city not in toSend:
					toSend[city] = recursoXciudad
			break

		espacios_disponibles = [ ciudadesDestino[city]['disponible'] for city in ciudadesDestino if city not in toSend ]
		totalEspacioDisponible = sum( espacios_disponibles )
		restanteAEnviar = min(restanteAEnviar, totalEspacioDisponible)
		recursoXciudad = restanteAEnviar // len(espacios_disponibles)


	rutas = []
	for idCiudad in ciudadesDestino:
		ciudadD = ciudadesDestino[idCiudad]
		idIsla = ciudadD['islandId']
		faltante = toSend[idCiudad]
		for idCiudadOrigen in ciudadesOrigen:
			if faltante == 0:
				break

			ciudadO = ciudadesOrigen[idCiudadOrigen]
			recursoDisponible = ciudadO['disponible']
			for ruta in rutas:
				origen = ruta[0]
				rec = ruta[recurso + 3]
				if origen['id'] == idCiudadOrigen:
					recursoDisponible -= rec

			enviar = min(faltante, recursoDisponible)
			disponible = ciudadD['disponible']
			if disponible == 0 or enviar == 0:
				continue

			if disponible < enviar:
				faltante = 0
				enviar = disponible
			else:
				faltante -= enviar

			toSendArr = [0] * len(materials_names)
			toSendArr[recurso] = enviar
			ruta = (ciudadO, ciudadD, idIsla, *toSendArr)

			rutas.append(ruta)

	return rutas
