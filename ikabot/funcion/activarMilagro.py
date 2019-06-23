#! /usr/bin/env python3
# -*- coding: utf-8 -*-

#from ikabot.helpers.pedirInfo import read

import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.pedirInfo import *

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
		if isla['wonder'] not in [ isla['wonder'] for isla in islas ]:
			islas.append(isla)

	ids, citys = getIdsDeCiudades(s)
	ciudadesReligiosas = []
	for idCiudad in ids:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		if ciudad['islandId'] in [ isla['id'] for isla in islas ]:
			if ciudad['islandId'] not in [ ciudad['islandId'] for ciudad in ciudadesReligiosas ]:
				if 'temple' in [ edificio['building'] for edificio in ciudad['position'] ]:
					ciudadesReligiosas.append(ciudad)
					for isla in islas:
						if isla['id'] == ciudad['islandId']:
							isla['activable'] = True
							isla['city'] = ciudad
							break

	return [ isla for isla in islas if isla['activable'] ]

def activarMilagro(s):
	banner()

	islas = obtenerMilagrosDisponibles(s)
	i = 1
	print('(0) Salir')
	for isla in islas:
		print('({:d}) {}'.format(i, isla['wonderName']))
		i += 1
	input()
	exit()
