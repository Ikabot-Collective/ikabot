#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import math
import json
from decimal import *
from ikabot.config import *
from ikabot.helpers.varios import wait
from ikabot.helpers.getJson import getCity
from ikabot.helpers.naval import *

def sendGoods(s, originCityId, destinationCityId, islandId, ships, send):
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
	ships : int
		integer representing the amount of ships needed to execute the route
	send : array
		array of resources to send
	"""

	# this can fail if a random request is made in between this two posts
	while True:
		html = s.get()
		city = getCity(html)
		currId = city['id']
		data = {'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': 'REQUESTID', 'oldView': 'city', 'cityId': originCityId, 'backgroundView': 'city', 'currentCityId': currId, 'ajax': '1'}
		s.post(payloadPost=data)

		data = {'action': 'transportOperations', 'function': 'loadTransportersWithFreight', 'destinationCityId': destinationCityId, 'islandId': islandId, 'oldView': '', 'position': '', 'avatar2Name': '', 'city2Name': '', 'type': '', 'activeTab': '', 'transportDisplayPrice': '0', 'premiumTransporter': '0', 'minusPlusValue': '500', 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': ships, 'backgroundView': 'city', 'currentCityId': originCityId, 'templateView': 'transport', 'currentTab': 'tabSendTransporter', 'actionRequest': 'REQUESTID', 'ajax': '1'}

		# add amounts of resources to send
		for i in range(len(send)):
			key = 'cargo_resource' if i == 0 else 'cargo_tradegood{:d}'.format(i)
			data[key] = send[i]

		resp = s.post(payloadPost=data)
		resp = json.loads(resp, strict=False)
		if resp[3][1][0]['type'] == 10:
			break

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
		(ciudadOrigen, ciudadDestino, idIsla, *toSend) = ruta
		destId = ciudadDestino['id']

		while sum(toSend) > 0:
			barcosDisp = waitForArrival(s)
			storageCapacityInShips = barcosDisp * 500

			html = s.get(urlCiudad + destId)
			ciudadDestino = getCity(html)
			storageCapacityInCity = ciudadDestino['freeSpaceForResources']

			send = []
			for i in range(len(toSend)):
				min_val = min(toSend[i], storageCapacityInShips, storageCapacityInCity[i])
				send.append(min_val)
				storageCapacityInShips -= send[i]
				toSend[i] -= send[i]

			cantEnviada = sum(send)
			if cantEnviada == 0:
				# no space available
				# wait an hour and try again
				wait(60 * 60)
				continue

			barcos = int(math.ceil((Decimal(cantEnviada) / Decimal(500))))
			sendGoods(s, ciudadOrigen['id'], ciudadDestino['id'], idIsla, barcos, send)

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
	url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest=REQUESTID&ajax=1'.format(idCiudad)
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
