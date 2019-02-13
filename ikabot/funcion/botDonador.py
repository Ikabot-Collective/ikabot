#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.gui import *
from ikabot.helpers.process import forkear
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.recursos import getRecursosDisponibles

def botDonador(s):
	if botValido(s) is False:
		return

	banner()
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	ciudades_dict = {}
	bienes = {'1': '(V)', '2': '(M)', '3': '(C)', '4': '(A)'}
	for idCiudad in idsCiudades:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		tradegood = ciudades[idCiudad]['tradegood']
		bien = bienes[tradegood]
		print('En la ciudad {} {}, ¿Desea donar al aserradero o al bien de cambio? [a/b]'.format(ciudad['cityName'], bien))
		rta = read(values=['a', 'A', 'b', 'B'])
		tipo = 'resource' if rta.lower() == 'a' else 'tradegood'
		ciudades_dict[idCiudad] = {'isla': ciudad['islandId'], 'tipo': tipo}

	print('Se donará todos los días.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nDono todos los días\n'
	setInfoSignal(s, info)
	try:
		do_it(s, idsCiudades, ciudades_dict)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s, idsCiudades, ciudades_dict):
	while True:
		for idCiudad in idsCiudades:
			html = s.get(urlCiudad + idCiudad)
			madera = getRecursosDisponibles(html)[0]
			idIsla = ciudades_dict[idCiudad]['isla']
			tipo = ciudades_dict[idCiudad]['tipo']
			s.post(payloadPost={'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': madera, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})
		msg = 'Done automaticamente.'
		sendToBotDebug(msg, debugON_botDonador)
		time.sleep(24*60*60)
