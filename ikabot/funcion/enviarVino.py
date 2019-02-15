#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.planearViajes import planearViajes
from ikabot.helpers.recursos import getRecursosDisponibles
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import banner

def enviarVino(s):
	banner()
	vinoTotal = 0
	dict_idVino_diponible = {}
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	ciudadesVino = {}
	for idCiudad in idsCiudades:
		esVino =  ciudades[idCiudad]['tradegood'] == '1'
		if esVino:
			html = s.get(urlCiudad + idCiudad)
			ciudad = getCiudad(html)
			recursos = getRecursosDisponibles(html)
			disponible = int(recursos[1]) - 1000 # dejo 1000 por las dudas
			ciudad['disponible'] = disponible if disponible > 0 else 0
			vinoTotal += ciudad['disponible']
			ciudadesVino[idCiudad] = ciudad
	aEnviar = len(ciudades) - len(ciudadesVino)
	vinoXciudad = int(vinoTotal / aEnviar)
	maximo = addPuntos(vinoXciudad)

	if vinoXciudad > 100000:
		maximo = maximo[:-6] + '00.000'
	elif vinoXciudad > 10000:
		maximo = maximo[:-5] + '0.000'
	elif vinoXciudad > 1000:
		maximo = maximo[:-3] + '000'
	elif vinoXciudad > 100:
		maximo = maximo[:-2] + '00'
	elif vinoXciudad > 10:
		maximo = maximo[:-1] + '0'
	print('Se puede enviar como máximo {} a cada ciudad'.format(maximo))
	cantidad = read(msg='¿Cuanto vino enviar a cada ciudad?:', min=0, max=vinoXciudad)

	print('\nPor enviar {} de vino a cada ciudad'.format(addPuntos(cantidad)))
	print('¿Proceder? [Y/n]')
	rta = read()
	if rta.lower() == 'n':
		return

	forkear(s)
	if s.padre is True:
		return

	rutas = []
	for idCiudadDestino in idsCiudades:
		if idCiudadDestino not in ciudadesVino:
			htmlD = s.get(urlCiudad + idCiudadDestino)
			ciudadD = getCiudad(htmlD)
			idIsla = ciudadD['islandId']
			faltante = cantidad
			for idCiudadOrigen in ciudadesVino:
				if faltante == 0:
					break
				ciudadO = ciudadesVino[idCiudadOrigen]
				vinoDisponible = ciudadO['disponible']
				for ruta in rutas:
					(origen, _, _, _, vn, _, _, _) = ruta
					if origen['id'] == idCiudadOrigen:
						vinoDisponible -= vn
				enviar = faltante if vinoDisponible > faltante else vinoDisponible
				faltante -= enviar
				ruta = (ciudadO, ciudadD, idIsla, 0, enviar, 0, 0, 0)
				rutas.append(ruta)

	info = '\nEnviar vino\n'
	for ruta in rutas:
		(ciudadO, ciudadD, idIsla, md, vn, mr, cr, az) = ruta
		info = info + '{} -> {}\nVino: {}\n'.format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(vn))
	setInfoSignal(s, info)
	try:
		planearViajes(s, rutas)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()
