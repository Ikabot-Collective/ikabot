#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import esperar
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import addPuntos
t = gettext.translation('entrenarTropas',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def entrenar(s, ciudad, entrenamiento):
	payload = {'301': '0', '302': '0', '303': '1', '304': '0', '305': '0', '306': '0', '307': '0', '308': '0', '309': '0', '310': '0', '311': '0', '312': '0', '313': '0', '315': '0', 'action': 'CityScreen', 'function': 'buildUnits', 'actionRequest': s.token(), 'cityId': ciudad['id'], 'position': pos, 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'barracks', 'ajax': '1'}
	#s.post(payloadPost=payload)

def esperarEntrenamiento(s, ciudad):
	params = {'view': 'barracks', 'cityId': ciudad['id'], 'position': ciudad['pos'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'actionRequest': s.token(), 'ajax': '1'}
	data = s.post(params=params)
	data = json.loads(data, strict=False)
	html = data[1][1][1]
	segundos = re.search(r'\'buildProgress\', (\d+),', html)
	if segundos:
		segundos = segundos.group(1)
		esperar(segundos + 5)

def planearEntrenamientos(s, ciudad, entrenamientos):
	while True:
		total = 0
		for entrenamiento in entrenamientos:
			for tropa in entrenamiento:
				total += tropa['cantidad']
		if total == 0:
			return
	for entrenamiento in entrenamientos:
		esperarEntrenamiento(s, ciudad)
		html = s.get(urlCiudad + ciudad['id'])
		ciudadanosDisp = re.search(r'js_GlobalMenu_citizens">(.*?)</span>', html).group(1)
		ciudadanosDisp = int(ciudadanosDisp.replace(',', ''))
		recursos = getRecursosDisponibles(html, num=True)
		maderaDisp = recursos[0]
		azufreDisp = recursos[4]
		for tropa in entrenamiento:

			limitante = maderaDisp // tropa['costs']['wood']
			if limitante < tropa['cantidad']:
				tropa['entrenar'] = limitante
			else:
				tropa['entrenar'] = tropa['cantidad']

			limitante = azufreDisp // tropa['costs']['sulfur']
			if limitante < tropa['entrenar']:
				tropa['entrenar'] = limitante

			limitante = ciudadanosDisp // tropa['costs']['citizens']
			if limitante < tropa['entrenar']:
				tropa['entrenar'] = limitante

			tropa['cantidad'] -= tropa['entrenar']
			maderaDisp -= tropa['costs']['wood'] * tropa['entrenar']
			azufreDisp -= tropa['costs']['sulfur'] * tropa['entrenar']
			ciudadanosDisp -= tropa['costs']['citizens'] * tropa['entrenar']
		entrenar(s, ciudad, entrenamiento)

def entrenarTropas(s):
	banner()
	print('¿En qué ciudad quiere entrenar las tropas?')
	ciudad = elegirCiudad(s)
	for i in range(len(ciudad['position'])):
		if ciudad['position'][i]['building'] == 'barracks':
			pos = str(i)
			ciudad['pos'] = pos
			break

	params = {'view': 'barracks', 'cityId': ciudad['id'], 'position': ciudad['pos'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'actionRequest': s.token(), 'ajax': '1'}
	data = s.post(params=params)
	data = json.loads(data, strict=False)
	unidades_info = data[2][1]

	banner()
	i = 1
	unidades = []
	maxSize = 0
	while 'js_barracksSlider{:d}'.format(i) in unidades_info:
		# {"identifier":"phalanx","unit_type_id":303,"costs":{"citizens":1,"wood":27,"sulfur":30,"upkeep":3,"completiontime":71.169695412658},"local_name":"Hoplita"}
		info = unidades_info['js_barracksSlider{:d}'.format(i)]['slider']['control_data']
		info = json.loads(info, strict=False)
		if maxSize < len(info['local_name']):
			maxSize = len(info['local_name'])
		unidades.append(info)
		i += 1

	entrenamientos = []
	while True:
		print('Entrenar:')
		for unidad in unidades:
			cantidad = read(msg='{}{}:'.format(' '*(maxSize-len(unidad['local_name'])), unidad['local_name']), min=0, empty=True)
			if cantidad == '':
				cantidad = 0
			unidad['cantidad'] = cantidad

		print('\nCosto total:')
		costo = {'ciudadanos': 0, 'madera': 0, 'azufre': 0}
		for unidad in unidades:
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
			break # ?

		entrenamientos.append(unidades)

		print('\n¿Quiere entrenar más tropas al terminar? [y/N]')
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'y':
			print('')
			continue
		else:
			break

	planearEntrenamientos(s, ciudad, entrenamientos)
	exit(input())

