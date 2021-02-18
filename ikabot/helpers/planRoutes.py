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

def sendGoods(session, originCityId, destinationCityId, islandId, ships, send):
	"""This function will execute one route
	Parameters
	----------
	session : ikabot.web.session.Session
		Session object
	originCityId : int
		integer representing the ID of the origin city
	destinationCityId : int
		integer representing the ID of the destination city
	islandId : int
		integer representing the ID of the destination city's island
	ships : int
		integer representing the amount of ships needed to execute the route
	send : list
		array of resources to send
	"""

	# this can fail if a random request is made in between this two posts
	while True:
		html = session.get()
		city = getCity(html)
		currId = city['id']
		data = {'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': actionRequest, 'oldView': 'city', 'cityId': originCityId, 'backgroundView': 'city', 'currentCityId': currId, 'ajax': '1'}
		session.post(payloadPost=data)

		data = {'action': 'transportOperations', 'function': 'loadTransportersWithFreight', 'destinationCityId': destinationCityId, 'islandId': islandId, 'oldView': '', 'position': '', 'avatar2Name': '', 'city2Name': '', 'type': '', 'activeTab': '', 'transportDisplayPrice': '0', 'premiumTransporter': '0', 'minusPlusValue': '500', 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': ships, 'backgroundView': 'city', 'currentCityId': originCityId, 'templateView': 'transport', 'currentTab': 'tabSendTransporter', 'actionRequest': actionRequest, 'ajax': '1'}

		# add amounts of resources to send
		for i in range(len(send)):
			key = 'cargo_resource' if i == 0 else 'cargo_tradegood{:d}'.format(i)
			data[key] = send[i]

		resp = session.post(payloadPost=data)
		resp = json.loads(resp, strict=False)
		if resp[3][1][0]['type'] == 10:
			break
		elif resp[3][1][0]['type'] == 11:
			wait(getMinimumWaitingTime(session))
		time.sleep(5)

def executeRoutes(session, routes):
	"""This function will execute all the routes passed to it, regardless if there are enough ships available to do so
	Parameters
	----------
	session : ikabot.web.session.Session
		Session object
	routes : list
		a list of tuples, each of which represent a route. A route is defined like so : (originCity,destinationCity,islandId,wood,wine,marble,crystal,sulfur). originCity and destintionCity should be passed as City objects
	"""
	for route in routes:
		(origin_city, destination_city, island_id, *toSend) = route
		destination_city_id = destination_city['id']

		while sum(toSend) > 0:
			ships_available = waitForArrival(session)
			storageCapacityInShips = ships_available * 500

			html = session.get(city_url + str(origin_city['id']))
			origin_city = getCity(html)
			html = session.get(city_url + str(destination_city_id))
			destination_city = getCity(html)
			foreign = str(destination_city['id']) != str(destination_city_id)
			if foreign is False:
				storageCapacityInCity = destination_city['freeSpaceForResources']

			send = []
			for i in range(len(toSend)):
				if foreign is False:
					min_val = min(origin_city['recursos'][i], toSend[i], storageCapacityInShips, storageCapacityInCity[i])
				else:
					min_val = min(origin_city['recursos'][i], toSend[i], storageCapacityInShips)
				send.append(min_val)
				storageCapacityInShips -= send[i]
				toSend[i] -= send[i]

			resources_to_send = sum(send)
			if resources_to_send == 0:
				# no space available
				# wait an hour and try again
				wait(60 * 60)
				continue

			available_ships = int(math.ceil((Decimal(resources_to_send) / Decimal(500))))
			sendGoods(session, origin_city['id'], destination_city_id, island_id, available_ships, send)

def getMinimumWaitingTime(session):
	"""This function returns the time needed to wait for the closest fleet to arrive. If all ships are unavailable, this represents the minimum time needed to wait for any ships to become available. A random waiting time between 0 and 10 seconds is added to the waiting time to avoid race conditions between multiple concurrently running processes.
	Parameters
	----------
	session : ikabot.web.session.Session
		Session object

	Returns
	-------
	timeToWait : int
		the minimum waiting time for the closest fleet to arrive
	"""
	html = session.get()
	idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
	url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, actionRequest)
	posted = session.post(url)
	postdata = json.loads(posted, strict=False)
	militaryMovements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
	current_time = int(postdata[0][1]['time'])
	delivered_times = []
	for militaryMovement in [ mv for mv in militaryMovements if mv['isOwnArmyOrFleet'] ]:
		remaining_time = int(militaryMovement['eventTime']) - current_time
		delivered_times.append(remaining_time)
	if delivered_times:
		return min(delivered_times) + random.uniform(0,10)
	else:
		return 0

def waitForArrival(session):
	"""This function will return the number of available ships, and if there aren't any, it will wait for the closest fleet to arrive and then return the number of available ships
	Parameters
	----------
	session : ikabot.web.session.Session
		Session object

	Returns
	-------
	ships : int
		number of available ships
	"""
	available_ships = getAvailableShips(session)
	while available_ships == 0:
		minimum_waiting_time_for_ship = getMinimumWaitingTime(session)
		wait( minimum_waiting_time_for_ship )
		available_ships = getAvailableShips(session)
	return available_ships
