#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import gettext
from ikabot.config import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.gui import banner
#import math
#import traceback
#from decimal import *
#from ikabot.helpers.process import forkear
#from ikabot.helpers.varios import addPuntos
#from ikabot.helpers.gui import enter, banner
#from ikabot.helpers.getJson import getCiudad
#from ikabot.helpers.signals import setInfoSignal
#from ikabot.helpers.planearViajes import esperarLlegada
#from ikabot.helpers.pedirInfo import getIdsDeCiudades, read
#from ikabot.helpers.botComm import *
#from ikabot.helpers.recursos import *

t = gettext.translation('construirEdificio', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def construirEdificio(s):

	print(_('Ciudad donde contruir:'))
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
			html = json.loads(resp, strict=False)[1][1][1]
			matches = re.findall(r'<li class="building (.+?)">\s*<div class="buildinginfo">\s*<div title="(.+?)"\s*class="buildingimg .+?"\s*onclick="ajaxHandlerCall\(\'.*?buildingId=(\d+)&', html)
			for match in matches:
				edificios.append({'building': match[0], 'name': match[1], 'buildingId': match[2], 'type': tipo})

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
	s.post(params=params, noIndex=True)
	exit(input())

