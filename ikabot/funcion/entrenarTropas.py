#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import addPuntos
#from ikabot.helpers.pedirInfo import read
#from ikabot.helpers.getJson import getCiudad

t = gettext.translation('entrenarTropas',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def entrenarTropas(s):
	banner()
	print('¿En qué ciudad quiere entrenar las tropas?')
	ciudad = elegirCiudad(s)
	for i in range(len(ciudad['position'])):
		if ciudad['position'][i]['building'] == 'barracks':
			pos = str(i)
			break

	params = {'view': 'barracks', 'cityId': ciudad['id'], 'position': pos, 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'actionRequest': s.token(), 'ajax': '1'}
	data = s.post(params=params)
	data = json.loads(data, strict=False)
	html = data[1][1][1]
	unidades = data[2][1]

	banner()
	print('Entrenar:')
	i = 1
	infoUnidades = []
	maxSize = 0
	while 'js_barracksSlider{:d}'.format(i) in unidades:
		# {"identifier":"phalanx","unit_type_id":303,"costs":{"citizens":1,"wood":27,"sulfur":30,"upkeep":3,"completiontime":71.169695412658},"local_name":"Hoplita"}
		info = unidades['js_barracksSlider{:d}'.format(i)]['slider']['control_data']
		info = json.loads(info, strict=False)
		if maxSize < len(info['local_name']):
			maxSize = len(info['local_name'])
		infoUnidades.append(info)
		i += 1
	for unidad in infoUnidades:
		cantidad = read(msg='{}{}:'.format(' '*(maxSize-len(unidad['local_name'])), unidad['local_name']), min=0, empty=True)
		if cantidad == '':
			cantidad = 0
		unidad['cantidad'] = cantidad

	print('\nCosto total:')
	costo = {'ciudadanos': 0, 'madera': 0, 'azufre': 0}
	for unidad in infoUnidades:
		costo['ciudadanos'] += unidad['costs']['citizens'] * unidad['cantidad']
		costo['madera'] += unidad['costs']['wood'] * unidad['cantidad']
		if 'sulfur' in unidad['costs']:
			costo['azufre'] += unidad['costs']['sulfur'] * unidad['cantidad']
	print('Ciudadanos: {}'.format(addPuntos(costo['ciudadanos'])))
	print('    Madera: {}'.format(addPuntos(costo['madera'])))
	print('    Azufre: {}'.format(addPuntos(costo['azufre'])))

	print('\nProceder? [Y/n]')
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		return

	exit(input())

	payload = {'301': '0', '302': '0', '303': '1', '304': '0', '305': '0', '306': '0', '307': '0', '308': '0', '309': '0', '310': '0', '311': '0', '312': '0', '313': '0', '315': '0', 'action': 'CityScreen', 'function': 'buildUnits', 'actionRequest': s.token(), 'cityId': ciudad['id'], 'position': pos, 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'barracks', 'ajax': '1'}
	#s.post(payloadPost=payload)
