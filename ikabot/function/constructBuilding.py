#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *

t = gettext.translation('constructBuilding', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def constructBuilding(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		print(_('City where to build:'))
		city = chooseCity(s)
		banner()

		# list of free spaces in the selected city
		free_spaces = [ buildings for buildings in city['position'] if buildings['building'] == 'empty' ]

		# get a list of all the posible buildings that can be built
		buildings = []
		# different buildings can be built in different areas
		type_spaces = ['sea', 'land', 'shore', 'wall']
		for type_space in type_spaces:
			free_spaces_of_type = [ free_space for free_space in free_spaces if free_space['type'] == type_space ]
			if len(free_spaces_of_type) > 0:
				# we take any space in the desired area
				free_space_of_type = free_spaces_of_type[0]
				params = {'view': 'buildingGround', 'cityId': city['id'], 'position': free_space_of_type['position'], 'backgroundView': 'city', 'currentCityId': city['id'], 'actionRequest': 'REQUESTID', 'ajax': '1'}
				resp = s.post(params=params, noIndex=True)
				resp = json.loads(resp, strict=False)[1][1]
				if resp == '':
					continue
				html = resp[1]
				matches = re.findall(r'<li class="building (.+?)">\s*<div class="buildinginfo">\s*<div title="(.+?)"\s*class="buildingimg .+?"\s*onclick="ajaxHandlerCall\(\'.*?buildingId=(\d+)&', html)
				# add the buildings that can be built in this area
				for match in matches:
					buildings.append({'building': match[0], 'name': match[1], 'buildingId': match[2], 'type': type_space})

		if len(buildings) == 0:
			print(_('No building can be built.'))
			enter()
			e.set()
			return

		# show list of buildings to the user
		print(_('What building do you want to build?\n'))
		i = 0
		for building in buildings:
			i += 1
			print('({:d}) {}'.format(i, building['name']))
		rta = read(min=1, max=i)
		banner()

		# show posible positions for the selected building
		building = buildings[rta - 1]
		print('{}\n'.format(building['name']))
		opciones = [ espacio for espacio in city['position'] if espacio['building'] == 'empty' and espacio['type'] == building['type'] ]
		if len(opciones) == 1:
			opcion = opciones[0]
		else:
			print(_('In which position do you want to build?\n'))
			i = 0
			for opcion in opciones:
				i += 1
				print('({:d}) {}'.format(i, opcion['position']))
			rta = read(min=1, max=i)
			opcion = opciones[rta - 1]
			banner()

		# build it
		params = {'action': 'CityScreen', 'function': 'build', 'cityId': city['id'], 'position': opcion['position'], 'building': building['buildingId'], 'backgroundView': 'city', 'currentCityId': city['id'], 'templateView': 'buildingGround', 'actionRequest': 'REQUESTID', 'ajax': '1'}
		resp = s.post(params=params, noIndex=True)
		msg = json.loads(resp, strict=False)[3][1][0]['text']
		print(msg)
		enter()
		e.set()
	except KeyboardInterrupt:
		e.set()
		return
