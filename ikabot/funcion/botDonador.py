#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import enter
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.recursos import getRecursosDisponibles

def botDonador(s):
	if botValido(s) is False:
		return
	print('¿Donar a aserraderos o a bienes de cambio? [a/b]')
	rta = read(values=['a', 'A', 'b', 'B'])
	tipo = 'resource' if rta.lower() == 'a' else 'tradegood'
	print('Se donará todos los días.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nDono todos los días\n'
	setInfoSignal(s, info)
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	ciudades_dict = {}
	for idCiudad in idsCiudades:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		ciudades_dict[idCiudad] = ciudad['islandId']
	try:
		do_it(s, tipo, idsCiudades, ciudades_dict)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(s, msg)
		s.logout()

def do_it(s, tipo, idsCiudades, ciudades_dict):
	while True:
		for idCiudad in idsCiudades:
			html = s.get(urlCiudad + idCiudad)
			madera = getRecursosDisponibles(html)[0]
			idIsla = ciudades_dict[idCiudad]
			s.post(payloadPost={'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': madera, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})
		time.sleep(24*60*60)
