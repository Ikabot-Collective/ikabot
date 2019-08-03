#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *

t = gettext.translation('construirEdificio', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def construirEdificio(s):
	banner()

	print(_('Ciudad donde construir:'))
	ciudad = elegirCiudad(s)
	banner()

	espacios = [ edificio for edificio in ciudad['position'] if edificio['building'] == 'empty' ]

	edificios = []
	tipos = ['sea', 'land', 'shore', 'wall']
	for tipo in tipos:
		espacios_tipo = [ espacio for espacio in espacios if espacio['type'] == tipo ]
		if len(espacios_tipo) > 0:
			params = {'view': 'buildingGround', 'cityId': ciudad['id'], 'position': espacios_tipo[0]['position'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'actionRequest': s.token(), 'ajax': '1'}
			resp = s.post(params=params, noIndex=True)
			resp = json.loads(resp, strict=False)[1][1]
			if resp == '':
				continue
			html = resp[1]
			matches = re.findall(r'<li class="building (.+?)">\s*<div class="buildinginfo">\s*<div title="(.+?)"\s*class="buildingimg .+?"\s*onclick="ajaxHandlerCall\(\'.*?buildingId=(\d+)&', html)
			for match in matches:
				edificios.append({'building': match[0], 'name': match[1], 'buildingId': match[2], 'type': tipo})

	if len(edificios) == 0:
		print(_('No se puede construir ningún edificio'))
		enter()
		return

	print(_('¿Qué edificio quiere construir?\n'))
	i = 0
	for edificio in edificios:
		i += 1
		print('({:d}) {}'.format(i, edificio['name']))
	rta = read(min=1, max=i)
	banner()
	edificio = edificios[rta - 1]
	print('{}\n'.format(edificio['name']))
	opciones = [ espacio for espacio in ciudad['position'] if espacio['building'] == 'empty' and espacio['type'] == edificio['type'] ]
	if len(opciones) == 1:
		opcion = opciones[0]
	else:
		print(_('¿En qué posición quiere contruir?\n'))
		i = 0
		for opcion in opciones:
			i += 1
			print('({:d}) {}'.format(i, opcion['position']))
		rta = read(min=1, max=i)
		opcion = opciones[rta - 1]
		banner()
	params = {'action': 'CityScreen', 'function': 'build', 'cityId': ciudad['id'], 'position': opcion['position'], 'building': edificio['buildingId'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'buildingGround', 'actionRequest': s.token(), 'ajax': '1'}
	resp = s.post(params=params, noIndex=True)
	msg = json.loads(resp, strict=False)[3][1][0]['text']
	print(msg)
	enter()
