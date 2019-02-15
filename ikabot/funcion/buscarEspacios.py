#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.pedirInfo import getIdsdeIslas
from ikabot.helpers.getJson import getIsla
from ikabot.helpers.process import forkear

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
	try:
		do_it(s, idIslas)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s, idIslas):
	isla_ciudades = {}
	while True:
		for idIsla in idIslas:
			html = s.get(urlIsla + idIsla)
			isla = getIsla(html)
			ciudades = []
			for ciudad in isla['cities']:
				if ciudad['type'] != 'empty':
					ciudades.append(ciudad)

			if idIsla in isla_ciudades:
				ciudadesAntes = isla_ciudades[idIsla]

				# alguien desaparecio
				for cityAntes in ciudadesAntes:
					encontrado = False
					for ciudad in ciudades:
						if ciudad['id'] == cityAntes['id']:
							encontrado = True
							break
					if encontrado is False:
						msg = 'la ciudad {} del jugador {} desapareció en {} {}:{} {}'.format(cityAntes['name'], cityAntes['Name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
						sendToBot(msg)

				# alguien fundo
				for ciudad in ciudades:
					encontrado = False
					for cityAntes in ciudadesAntes:
						if ciudad['id'] == cityAntes['id']:
							encontrado = True
							break
					if encontrado is False:
						msg = '{} fundó {} en {} {}:{} {}'.format(ciudad['Name'], ciudad['name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
						sendToBot(msg)

			isla_ciudades[idIsla] = ciudades
		time.sleep(1*60*60)
