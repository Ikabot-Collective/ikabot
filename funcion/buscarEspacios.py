#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from config import *
from helpers.botComm import *
from helpers.gui import enter
from helpers.signals import setInfoSignal
from helpers.pedirInfo import getIdsdeIslas
from helpers.getJson import getIsla
from helpers.process import forkear

def buscarEspacios(s):
	if botValido(s) is False:
		return
	print('Se buscarán espacios nuevos cada hora.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nBusco espacios nuevos en las islas cada 1 hora\n'
	setInfoSignal(s, info)
	idIslas = getIdsdeIslas(s)
	ciudades_espacios_dict = {}
	try:
		while True:
			for idIsla in idIslas:
				html = s.get(urlIsla + idIsla)
				isla = getIsla(html)
				espacios = 0
				ciudades = []
				for city in isla['cities']:
					if city['type'] == 'empty':
						espacios += 1
					else:
						ciudades.append(city)

				if idIsla in ciudades_espacios_dict:
					espaciosAntes = ciudades_espacios_dict[idIsla][1]
					ciudadesAntes = ciudades_espacios_dict[idIsla][0]
					ciudadesAhora = isla['cities']

					if espaciosAntes < espacios:
						# alguien desaparecio
						for cityAntes in ciudadesAntes:
							encontrado = False
							for cityAhora in ciudadesAhora:
								if cityAhora['type'] != 'empty' and cityAhora['id'] == cityAntes['id']:
									encontrado = True
									break
							if encontrado is False:
								msg = 'la ciudad {} del jugador {} desapareció en {} {}:{} {}'.format(cityAntes['name'], cityAntes['Name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
								sendToBot(s, msg)

					if espaciosAntes > espacios:
						# alguien fundo
						for cityAhora in ciudadesAhora:
							encontrado = False
							for cityAntes in ciudadesAntes:
								if cityAhora['type'] != 'empty' and cityAhora['id'] == cityAntes['id']:
									encontrado = True
									break
							if encontrado is False:
								msg = '{} fundó la ciudad {} en {} {}:{} {}'.format(cityAhora['Name'], cityAhora['name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
								sendToBot(s, msg)

				ciudades_espacios_dict[idIsla] = (ciudades, espacios)
			time.sleep(1*60*60)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(s, msg)
		s.logout()
