#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from helpers.signals import *
from helpers.pedirInfo import *
from helpers.getJson import *
from helpers.planearViajes import *
from helpers.recursos import *
from helpers.varios import *
from helpers.process import *
from helpers.gui import *

def enviarVino(s):
	banner()
	vinoTotal = 0
	dict_idVino_diponible = {}
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	for idCiudad in idsCiudades:
		esVino =  ciudades[idCiudad]['tradegood'] == '1'
		if esVino:
			html = s.get(urlCiudad + idCiudad)
			recursos = getRecursosDisponibles(html)
			dict_idVino_diponible[idCiudad] = int(recursos[1]) - 1000 # dejo 1000 por las dudas
			if dict_idVino_diponible[idCiudad] < 0:
				dict_idVino_diponible[idCiudad] = 0
			vinoTotal += dict_idVino_diponible[idCiudad]
	aEnviar = len(ciudades) - len(dict_idVino_diponible)
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
		noEsVino =  ciudades[idCiudadDestino]['tradegood'] != '1'
		if noEsVino:
			htmlD = s.get(urlCiudad + idCiudadDestino)
			ciudadD = getCiudad(htmlD)
			idIsla = ciudadD['islandId']
			faltante = cantidad
			for idCiudadOrigen in dict_idVino_diponible:
				if faltante == 0:
					break
				vinoDisponible = dict_idVino_diponible[idCiudadOrigen]
				for ruta in rutas:
					(origen, _, _, _, vn, _, _, _) = ruta
					if origen == idCiudadOrigen:
						vinoDisponible -= vn
				enviar = faltante if vinoDisponible > faltante else vinoDisponible
				faltante -= enviar
				ruta = (idCiudadOrigen, idCiudadDestino, idIsla, 0, enviar, 0, 0, 0)
				rutas.append(ruta)

	info = '\nEnviar vino\n'
	for ruta in rutas:
		(idciudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az) = ruta
		html = s.get(urlCiudad + idciudadOrigen)
		ciudadO = getCiudad(html)
		html = s.get(urlCiudad + idCiudadDestino)
		ciudadD = getCiudad(html)
		info = info + '{} -> {}\nVino: {}\n'.format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(vn))
	setInfoSignal(s, info)
	planearViajes(s, rutas)
	s.logout()
