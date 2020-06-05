#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.planearViajes import executeRoutes
from ikabot.helpers.recursos import *
from ikabot.helpers.varios import addDot
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.gui import banner

t = gettext.translation('repartirRecurso',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def repartirRecurso(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		print(_('¿Qué recurso quiere distribuir?'))
		print(_('(0) Salir'))
		for i in range(len(tipoDeBien)):
			print('({:d}) {}'.format(i+1, tipoDeBien[i]))
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
		print(_('\nSe realizarán los siguientes envios:\n'))
		for route in routes:
			print('{} -> {} : {} {}'.format(route[0]['name'], route[1]['name'], route[resource+3], tipoDeBien[resource])) #displays all routes to be executed in console

		print(_('\n¿Proceder? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			e.set()
			return

	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set() #this is where we give back control to main process

	info = _('\nDistribuyo {}\n').format(tipoDeBien[resource])
	setInfoSignal(s, info)

	try:
		pass
		#executeRoutes(s, routes) #plan trips for all the routes
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg) #sends message to telegram bot
	finally:
		s.logout()

def distribute_evenly(s, resource):
	resourceTotal = 0 #total number of selected resource
	(cityIDs, cities) = getIdsOfCities(s) #gets city ids

	originCities = {} #dictionary for origin cities
	destinationCities = {} #dictionary for destination cities
	allCities = {} #dictionary for all cities
	for cityID in cityIDs: #for each of the users cities

		html = s.get(urlCiudad + cityID) #load html from the get request for that particular city
		city = getCiudad(html) #convert the html to a city object

		resourceTotal += city['recursos'][resource] #the cities resources are added to the total
		allCities[cityID] = city #adds the city to all cities

	resourceAverage = resourceTotal // len(allCities) #calculate the resource average
	resourceTotal = 0
	for cityID in cityIDs: #iterate through all the cities and exclude the ones with less capacity than the resource average from calculations
		if allCities[cityID]['storageCapacity'] < resourceAverage:
			allCities.pop(cityID)
		else:
			resourceTotal += allCities[cityID]['recursos'][resource] #else add it to the total for recalculation

	resourceAverage = resourceTotal // len(allCities) #recalculate the resource average

	for cityID in allCities: #iterate through cities and classify them as origin or destination based on amount of resource above average
		if allCities[cityID]['recursos'][resource] > resourceAverage:
			originCities[cityID] = allCities[cityID]['recursos'][resource] - resourceAverage #sets the value to the amount of resource above average
		else:
			destinationCities[cityID] = resourceAverage - allCities[cityID]['recursos'][resource] #sets the value to the amount of resource below average

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

			toSendArr = [0] * len(tipoDeBien)
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
	dict_idVino_diponible = {}
	(idsCiudades, ciudades) = getIdsOfCities(s)
	ciudadesOrigen = {}
	ciudadesDestino = {}
	for idCiudad in idsCiudades:
		esTarget =  ciudades[idCiudad]['tradegood'] == str(recurso)
		if esTarget:
			html = s.get(urlCiudad + idCiudad)
			ciudad = getCiudad(html)
			ciudad['disponible'] = ciudad['recursos'][recurso]
			recursoTotal += ciudad['disponible']
			ciudadesOrigen[idCiudad] = ciudad
		else:
			html = s.get(urlCiudad + idCiudad)
			ciudad = getCiudad(html)
			ciudad['disponible'] = ciudad['freeSpaceForResources'][recurso]
			if ciudad['disponible'] > 0:
				ciudadesDestino[idCiudad] = ciudad

	if recursoTotal == 0:
		print(_('\nNo hay recursos para enviar.'))
		enter()
		return None
	if len(ciudadesDestino) == 0:
		print(_('\nNo hay espacio disponible para enviar recursos.'))
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
			enviar = faltante if recursoDisponible > faltante else recursoDisponible
			disponible = ciudadD['disponible']
			if disponible < enviar:
				faltante = 0
				enviar = disponible
			else:
				faltante -= enviar

			toSendArr = [0] * len(tipoDeBien)
			toSendArr[recurso] = enviar
			ruta = (ciudadO, ciudadD, idIsla, *toSendArr)

			rutas.append(ruta)

	return rutas
