#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import banner
from ikabot.helpers.recursos import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import forkear
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.planearViajes import planearViajes

t = gettext.translation('distributeResourcesEvenly',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def distributeResourcesEvenly(s):

	banner() #displays the ascii art banner

	print(_('¿Qué recurso quiere distribuir?'))
	print(_('(0) Salir'))
	for i in range(4):
		print('({:d}) {}'.format(i+1, tipoDeBien[i]))
	resource = read(min=0, max=5)
	if resource == 0:
		return
	resource -= 1

	resourceTotal = 0 #total number of selected resource
	(cityIDs, cities) = getIdsDeCiudades(s) #gets city ids
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
		if allCities[cityID]['capacidad'] < resourceAverage:
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

			# ROUTE BLOCK
			if resource == 0:
				route = (allCities[originCityID],allCities[destinationCityID],allCities[destinationCityID]['islandId'],toSend,0,0,0,0)
			elif resource == 1:
				route = (allCities[originCityID],allCities[destinationCityID],allCities[destinationCityID]['islandId'],0,toSend,0,0,0)
			elif resource == 2:
				route = (allCities[originCityID],allCities[destinationCityID],allCities[destinationCityID]['islandId'],0,0,toSend,0,0)
			elif resource == 3:
				route = (allCities[originCityID],allCities[destinationCityID],allCities[destinationCityID]['islandId'],0,0,0,toSend,0)
			elif resource == 4:
				route = (allCities[originCityID],allCities[destinationCityID],allCities[destinationCityID]['islandId'],0,0,0,0,toSend)
			routes.append(route)

			# ROUTE BLOCK
			if originCities[originCityID] > destinationCities[destinationCityID]:
				originCities[originCityID] -= destinationCities[destinationCityID] #remove the sent amount from the origin city's surplus
				destinationCities[destinationCityID] = 0 #set the amount of resources below average in destination city to 0
			else:
				destinationCities[destinationCityID] -= originCities[originCityID] #remove the sent amount from the amount of resources below average in current destination city
				originCities[originCityID] = 0 #set the amount of resources above average in origin city to 0

	banner()
	print(_('\nSe realizarán los siguientes envios:\n'))
	for route in routes:
		print('{} -> {} : {} {}'.format(route[0]['name'], route[1]['name'], route[resource+3], tipoDeBien[resource])) #displays all routes to be executed in console

	print(_('\nTodas las ciuaddes tendrán al rededor de {} de {}').format(addPuntos(resourceAverage), tipoDeBien[resource]))

	print(_('\n¿Proceder? [Y/n]'))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		return

	forkear(s) #forks the process.
	if s.padre is True:
		return

	info = _('\nDistribuyo {} de forma uniforme entre todas las ciudades\n').format(tipoDeBien[resource])
	setInfoSignal(s, info)

	try:
		planearViajes(s, routes) #plan trips for all the routes
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg) #sends message to telegram bot
	finally:
		s.logout()
