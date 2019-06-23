#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCiudad

t = gettext.translation('activarMilagro',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def obtenerMilagrosDisponibles(s):
	idsIslas = getIdsdeIslas(s)
	islas = []
	for idIsla in idsIslas:
		html = s.get(urlIsla + idIsla)
		isla = getIsla(html)
		isla['activable'] = False
		islas.append(isla)

	ids, citys = getIdsDeCiudades(s)
	for ciudad in citys:
		city = citys[ciudad]
		wonder = [ isla['wonder'] for isla in islas if city['coords'] == '[{}:{}] '.format(isla['x'], isla['y']) ][0]
		if wonder in [ isla['wonder'] for isla in islas if isla['activable'] ]:
			continue
		html = s.get(urlCiudad + str(city['id']))
		ciudad = getCiudad(html)
		if 'temple' in [ edificio['building'] for edificio in ciudad['position'] ]:
			for i in range( len( ciudad['position'] ) ):
				if ciudad['position'][i]['building'] == 'temple':
					ciudad['pos'] = str(i)
					break
			for isla in islas:
				if isla['id'] == ciudad['islandId']:
					isla['activable'] = True
					isla['city'] = ciudad
					break

	return [ isla for isla in islas if isla['activable'] ]

def activarMilagro(s):
	banner()

	islas = obtenerMilagrosDisponibles(s)
	print('¿Qué milagro quiere activar?')
	i = 0
	print('(0) Salir')
	for isla in islas:
		i += 1
		print('({:d}) {}'.format(i, isla['wonderName']))
	index = read(min=0, max=i)
	isla = islas[index]

	print('\nSe activará el milagro {}'.format(isla['wonderName']))
	print('¿Proceder? [Y/n]')
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		return
	params = {'action': 'CityScreen', 'cityId': isla['ciudad']['id'], 'function': 'activateWonder', 'position': isla['ciudad']['pos'], 'backgroundView': 'city', 'currentCityId': isla['ciudad']['id'], 'templateView': 'temple', 'actionRequest': s.token(), 'ajax': '1'}
	#s.post()
	input()
	exit()
