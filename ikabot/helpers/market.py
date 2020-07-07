#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.pedirInfo import getIdsOfCities

def getCommercialCities(session):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session

	Returns
	-------
	commercial_cities : list[dict]
	"""
	cities_ids = getIdsOfCities(session)[0]
	commercial_cities = []
	for city_id in cities_ids:
		html = session.get(city_url + city_id)
		city = getCity(html)
		for pos, building in enumerate(city['position']):
			if building['building'] == 'branchOffice':
				city['pos'] = pos
				html = getMarketHtml(session, city)
				positions = re.findall(r'<option.*?>(\d+)</option>', html)
				city['rango'] = int(positions[-1])
				commercial_cities.append(city)
				break
	return commercial_cities

def getMarketHtml(session, city):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	city : dict
	"""
	url = 'view=branchOffice&cityId={}&position={:d}&currentCityId={}&backgroundView=city&actionRequest={}&ajax=1'.format(city['id'], city['pos'], city['id'], actionRequest)
	data = session.post(url)
	json_data = json.loads(data, strict=False)
	return json_data[1][1][1]

def storageCapacityOfMarket(html):
	match = re.search(r'var\s*storageCapacity\s*=\s*(\d+);', html)
	if match:
		return int(match.group(1))
	else:
		return 0

def onSellInMarket(html):
	mad, vin, mar, cri, azu = re.findall(r'<input type="text" class="textfield"\s*size="\d+"\s*name=".*?"\s*id=".*?"\s*value="(\d+)"', html)
	return [int(mad), int(vin), int(mar), int(cri), int(azu)]
