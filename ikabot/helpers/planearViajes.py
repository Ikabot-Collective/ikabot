#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import math
import json
from decimal import *
from ikabot.config import *
from ikabot.helpers.varios import wait
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.naval import *

def sendGoods(s, originCityId, destinationCityId, islandId, wood, wine, marble, crystal, sulfur, ships):
	"""This function will execute one route
	Parameters
	----------
	s : Session
		Session object
	originCityId : int
		integer representing the ID of the origin city
	destinationCityId : int
		integer representing the ID of the destination city
	islandId : int
		integer representing the ID of the destination city's island
	wood : int
		integer representing the amount of wood to send
	wine : int
		integer representing the amount of wine to send
	marble : int
		integer representing the amount of marble to send
	crystal : int
		integer representing the amount of crystal to send
	sulfur : int
		integer representing the amount of sulfur to send
	ships : int
		integer representing the amount of ships needed to execute the route
	"""

	s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': originCityId, 'ajax': '1'}) 
	s.post(payloadPost={'action': 'transportOperations', 'function': 'loadTransportersWithFreight', 'destinationCityId': destinationCityId, 'islandId': islandId, 'oldView': '', 'position': '', 'avatar2Name': '', 'city2Name': '', 'type': '', 'activeTab': '', 'premiumTransporter': '0', 'minusPlusValue': '500', 'cargo_resource': wood, 'cargo_tradegood1': wine, 'cargo_tradegood2': marble, 'cargo_tradegood3': crystal, 'cargo_tradegood4': sulfur, 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': ships, 'backgroundView': 'city', 'currentCityId': originCityId, 'templateView': 'transport', 'currentTab': 'tabSendTransporter', 'actionRequest': s.token(), 'ajax': '1'})

def executeRoutes(s, routes):
	"""This function will execute all the routes passed to it, regardless if there are enough ships available to do so
	Parameters
	----------
	s : Session
		Session object
	routes : list
		a list of tuples, each of which represent a route. A route is defined like so : (originCity,destinationCity,islandId,wood,wine,marble,crystal,sulfur). originCity and destintionCity should be passed as City objects 
	"""
	for ruta in routes:
		(ciudadOrigen, ciudadDestino, idIsla, md, vn, mr, cr, az) = ruta
		destId = ciudadDestino.id
		while (md + vn + mr + cr + az) > 0:
			barcosDisp = waitForArrival(s)
			storageCapacityInShips = barcosDisp * 500

			html = s.get(urlCiudad + destId)
			ciudadDestino = getCiudad(html)
			storageCapacityInCity = ciudadDestino.freeSpaceForResources

			mdEnv = min(md, storageCapacityInShips, storageCapacityInCity[0])
			storageCapacityInShips -= mdEnv
			md -= mdEnv

			vnEnv = min(vn, storageCapacityInShips, storageCapacityInCity[1])
			storageCapacityInShips -= vnEnv
			vn -= vnEnv

			mrEnv = min(mr, storageCapacityInShips, storageCapacityInCity[2])
			storageCapacityInShips -= mrEnv
			mr -= mrEnv

			crEnv = min(cr, storageCapacityInShips, storageCapacityInCity[3])
			storageCapacityInShips -= crEnv
			cr -= crEnv

			azEnv = min(az, storageCapacityInShips, storageCapacityInCity[4])
			storageCapacityInShips -= azEnv
			az -= azEnv

			cantEnviada = mdEnv + vnEnv + mrEnv + crEnv + azEnv
			if cantEnviada == 0:
				# no space available
				# wait an hour and try again
				wait(60 * 60)
				continue

			barcos = int(math.ceil((Decimal(cantEnviada) / Decimal(500))))
			sendGoods(s, ciudadOrigen['id'], ciudadDestino['id'], idIsla, mdEnv, vnEnv, mrEnv, crEnv, azEnv, barcos)

def getMinimumWaitingTime(s):
	"""This function returns the time needed to wait for the closest fleet to arrive. If all ships are unavailable, this represents the minimum time needed to wait for any ships to become available
	Parameters
	----------
	s : Session
		Session object

	Returns
	-------
	timeToWait : int
		the minimum waiting time for the closest fleet to arrive 
	"""
	html = s.get()
	idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
	url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
	posted = s.post(url)
	postdata = json.loads(posted, strict=False)
	militaryMovements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
	tiempoAhora = int(postdata[0][1]['time'])
	tiemposDeEspera = []
	for militaryMovement in [ mv for mv in militaryMovements if mv['isOwnArmyOrFleet'] ]:
		tiempoRestante = int(militaryMovement['eventTime']) - tiempoAhora
		tiemposDeEspera.append(tiempoRestante)
	if tiemposDeEspera:
		return min(tiemposDeEspera)
	else:
		return 0

def waitForArrival(s):
	"""This function will return the number of available ships, and if there aren't any, it will wait for the closest fleet to arrive and then return the number of available ships
	Parameters
	----------
	s : Session
		Session object

	Returns
	-------
	ships : int
		number of available ships
	"""
	barcos = getAvailableShips(s)
	while barcos == 0:
		minTiempoDeEspera = getMinimumWaitingTime(s)
		wait( minTiempoDeEspera )
		barcos = getAvailableShips(s)
	return barcos
