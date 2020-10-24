#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from ikabot.helpers.resources import *

def getFreeCitizens(html):
	"""This function is used in the ``getCity`` function to determine the amount of free (idle) citizens in the given city.
	Parameters
	----------
	html : str
		a string representing html which is returned when sending a get request to view a city.

	Returns
	-------
	freeCitizens : int
		an integer representing the amount of free citizens in the given city.
	"""
	ciudadanosDisp = re.search(r'js_GlobalMenu_citizens">(.*?)</span>', html).group(1)
	return int(ciudadanosDisp.replace(',', '').replace('.', ''))

def onSale(html):
	"""This function is used in the ``getCity`` function to determine the amount of each resource which is on sale in the branch office
	Parameters
	----------
	html : str
		a string representing html which is returned when sending a get request to view a city.

	Returns
	-------
	onSale : list[int]
		a list containing 5 integers each of which representing the amount of that particular resource which is on sale in the given city. For more information about the order of the resources, refer to ``config.py``
	"""
	rta = re.search(r'branchOfficeResources: JSON\.parse\(\'{\\"resource\\":\\"(\d+)\\",\\"1\\":\\"(\d+)\\",\\"2\\":\\"(\d+)\\",\\"3\\":\\"(\d+)\\",\\"4\\":\\"(\d+)\\"}\'\)', html)
	if rta:
		return [ int(rta.group(1)), int(rta.group(2)), int(rta.group(3)), int(rta.group(4)), int(rta.group(5))]
	else:
		return [0, 0, 0, 0, 0]

def getIsland(html):
	"""This function uses the html passed to it as a string to extract, parse and return an Island object
	Parameters
	----------
	html : str
		the html returned when a get request to view the island is made. This request can be made with the following statement: ``s.get(urlIsla + islandId)``, where ``urlIsla`` is a string defined in ``config.py`` and ``islandId`` is the id of the island.

	Returns
	-------
	island : Island
		this function returns a json parsed Island object. For more information about this object refer to the github wiki page of Ikabot.
	"""
	isla = re.search(r'\[\["updateBackgroundData",([\s\S]*?),"specialServerBadges', html).group(1) + '}'

	isla = isla.replace('buildplace', 'empty')
	isla = isla.replace('xCoord', 'x')
	isla = isla.replace('yCoord', 'y')
	isla = isla.replace(',"owner', ',"')


	# {"id":idIsla,"name":nombreIsla,"x":,"y":,"good":numeroBien,"woodLv":,"goodLv":,"wonder":numeroWonder, "wonderName": "nombreDelMilagro","wonderLv":"5","cities":[{"type":"city","name":cityName,"id":cityId,"level":lvIntendencia,"Id":playerId,"Name":playerName,"AllyId":,"AllyTag":,"state":"vacation"},...}}
	isla = json.loads(isla, strict=False)
	isla['tipo'] = re.search(r'"tradegood":"(\d)"', html).group(1)
	isla['x'] = int(isla['x'])
	isla['y'] = int(isla['y'])

	return isla

def getCity(html):
	"""This function uses the ``html`` passed to it as a string to extract, parse and return a City object
	Parameters
	----------
	html : str
		the html returned when a get request to view the city is made. This request can be made with the following statement: ``s.get(urlCiudad + id)``, where urlCiudad is a string defined in ``config.py`` and id is the id of the city.

	Returns
	-------
	city : dict
		this function returns a json parsed City object. For more information about this object refer to the github wiki page of Ikabot.
	"""

	city = re.search(r'"updateBackgroundData",\s?([\s\S]*?)\],\["updateTemplateData"', html).group(1)
	city = json.loads(city, strict=False)

	city['Id'] = city.pop('ownerId')
	city['Name'] = city.pop('ownerName')
	city['x'] = int(city.pop('islandXCoord'))
	city['y'] = int(city.pop('islandYCoord'))
	city['cityName'] = city['name']

	i = 0
	for position in city['position']:
		position['position'] = i
		i += 1
		if 'level' in position:
			position['level'] = int(position['level'])
		position['isBusy'] = False
		if 'constructionSite' in position['building']:
			position['isBusy'] = True
			position['building'] = position['building'][:-17]
		elif 'buildingGround ' in position['building']:
			position['name'] = 'empty'
			position['type'] = position['building'].split(' ')[-1]
			position['building'] = 'empty'

	city['id'] = str(city['id'])
	city['propia'] = True
	city['recursos'] = getAvailableResources(html, num=True)
	city['storageCapacity'] = getWarehouseCapacity(html)
	city['ciudadanosDisp'] = getFreeCitizens(html)
	city['consumo'] = getWineConsumption(html)
	city['enventa'] = onSale(html)
	city['freeSpaceForResources'] = []
	for i in range(5):
		city['freeSpaceForResources'].append( city['storageCapacity'] - city['recursos'][i] - city['enventa'][i] )

	return city
