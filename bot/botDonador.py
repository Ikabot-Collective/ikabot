#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import botComm
import enter
import fork
import signals
import read
import getJson
import getVarios
import time

urlCiudad = 'view=city&cityId='

def botDonador(s):
	if botValido(s) is False:
		return
	print('¿Donar a aserraderos o a bienes de cambio? [a/b]')
	rta = read(values=['a', 'A', 'b', 'B'])
	tipo = 'resource' if rta.lower() == 'a' else 'tradegood'
	print('Se donará compulsivamente cada día.')
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
		while True:
			for idCiudad in idsCiudades:
				html = s.get(urlCiudad + idCiudad)
				madera = getRescursosDisponibles(html)[0]
				idIsla = ciudades_dict[idCiudad]
				s.post(payloadPost={'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': madera, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})
			time.sleep(24*60*60)
	except:
		msg = 'Ya no se donará.\n{}'.format(traceback.format_exc())
		sendToBot(s, msg)
		s.logout()