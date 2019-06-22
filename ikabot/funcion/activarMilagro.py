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
		islas.append(isla)

	ids, citys = getIdsDeCiudades(s)
	ciudadesReligiosas = []
	for idCiudad in ids:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		for edificio in ciudad['position']:
			if edificio['building'] == 'temple':
				ciudadesReligiosas.append(ciudad)
				for isla in islas:
					if isla['id'] == ciudad['islandId']:
						isla['activable'] = True
						break
				break
	wonders = [ isla['wonder'] for isla in islas if isla['activable'] ]
	return list(dict.fromkeys( wonders ))

def activarMilagro(s):
	banner()

	milagros = obtenerMilagrosDisponibles(s)
	nombres_milagros = {'8': 'Coloso'}
	i = 1
	print('(0) Salir')
	for milagro in milagros:
		print('({:d}) {}'.format(i, nombres_milagros[milagro]))
		i += 1
	input()
	exit()
