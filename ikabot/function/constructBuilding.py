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
                        languages=languages,
                        fallback=True)
_ = t.gettext

def constructBuilding(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	try:
		banner()

		print(_('City where to build:'))
		city = chooseCity(session)
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
				params = {'view': 'buildingGround', 'cityId': city['id'], 'position': free_space_of_type['position'], 'backgroundView': 'city', 'currentCityId': city['id'], 'actionRequest': actionRequest, 'ajax': '1'}
				buildings_response = session.post(params=params, noIndex=True)
				buildings_response = json.loads(buildings_response, strict=False)[1][1]
				if buildings_response == '':
					continue
				html = buildings_response[1]
				matches = re.findall(r'<li class="building (.+?)">\s*<div class="buildinginfo">\s*<div title="(.+?)"\s*class="buildingimg .+?"\s*onclick="ajaxHandlerCall\(\'.*?buildingId=(\d+)&', html)
				# add the buildings that can be built in this area
				for match in matches:
					buildings.append({'building': match[0], 'name': match[1], 'buildingId': match[2], 'type': type_space})

		if len(buildings) == 0:
			print(_('No building can be built.'))
			enter()
			event.set()
			return

		# show list of buildings to the user
		print(_('What building do you want to build?\n'))
		i = 0
		for building in buildings:
			i += 1
			print('({:d}) {}'.format(i, building['name']))
		selected_building_index = read(min=1, max=i)
		banner()

		# show posible positions for the selected building
		building = buildings[selected_building_index - 1]
		print('{}\n'.format(building['name']))
		options = [ position_id for position_id in city['position'] if position_id['building'] == 'empty' and position_id['type'] == building['type'] ]
		if len(options) == 1:
			option = options[0]
		else:
			print(_('In which position do you want to build?\n'))
			i = 0
			for option in options:
				i += 1
				print('({:d}) {}'.format(i, option['position']))
			selected_building_index = read(min=1, max=i)
			option = options[selected_building_index - 1]
			banner()

		# build it
		params = {'action': 'CityScreen', 'function': 'build', 'cityId': city['id'], 'position': option['position'], 'building': building['buildingId'], 'backgroundView': 'city', 'currentCityId': city['id'], 'templateView': 'buildingGround', 'actionRequest': actionRequest, 'ajax': '1'}
		buildings_response = session.post(params=params, noIndex=True)
		msg = json.loads(buildings_response, strict=False)[3][1][0]['text']
		print(msg)
		enter()
		event.set()
	except KeyboardInterrupt:
		event.set()
		return
