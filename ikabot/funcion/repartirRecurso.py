#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.planearViajes import executeRoutes
from ikabot.helpers.recursos import *
from ikabot.helpers.varios import addDot
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.gui import banner

t = gettext.translation('repartirRecurso',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def repartirRecurso(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		print(_('¿Qué recurso quiere repartir?'))
		print(_('(0) Salir'))
		print(_('(1) Vino'))
		print(_('(2) Marmol'))
		print(_('(3) Cristal'))
		print(_('(4) Azufre'))
		recurso = read(min=0, max=4)
		if recurso == 0:
			e.set() #give back control to main process
			return

		recursoTotal = 0
		dict_idVino_diponible = {}
		(idsCiudades, ciudades) = getIdsOfCities(s)
		ciudadesOrigen = {}
		ciudadesDestino = {}
		for idCiudad in idsCiudades:
			esTarget =  ciudades[idCiudad]['tradegood'] == str(recurso)
			if esTarget:
				html = s.get(urlCiudad + idCiudad)
				ciudad = getCiudad(html)
				ciudad['disponible'] = ciudad['recursos'][recurso]
				recursoTotal += ciudad['disponible']
				ciudadesOrigen[idCiudad] = ciudad
			else:
				html = s.get(urlCiudad + idCiudad)
				ciudad = getCiudad(html)
				ciudad['disponible'] = ciudad['freeSpaceForResources'][recurso]
				if ciudad['disponible'] > 0:
					ciudadesDestino[idCiudad] = ciudad

		if recursoTotal == 0:
			print(_('\nNo hay recursos para enviar.'))
			enter()
			e.set()
			return
		if len(ciudadesDestino) == 0:
			print(_('\nNo hay espacio disponible para enviar recursos.'))
			enter()
			e.set()
			return

		recursoXciudad = recursoTotal // len(ciudadesDestino)
		espacios_disponibles = [ ciudadesDestino[city]['disponible'] for city in ciudadesDestino ]
		totalEspacioDisponible = sum( espacios_disponibles )
		restanteAEnviar = min(recursoTotal, totalEspacioDisponible)
		toSend = {}

		while restanteAEnviar > 0:
			len_prev = len(toSend)
			for city in ciudadesDestino:
				ciudad = ciudadesDestino[city]
				if city not in toSend and ciudad['disponible'] < recursoXciudad:
					toSend[city] = ciudad['disponible']
					restanteAEnviar -= ciudad['disponible']

			if len(toSend) == len_prev:
				for city in ciudadesDestino:
					if city not in toSend:
						toSend[city] = recursoXciudad
				break

			espacios_disponibles = [ ciudadesDestino[city]['disponible'] for city in ciudadesDestino if city not in toSend ]
			totalEspacioDisponible = sum( espacios_disponibles )
			restanteAEnviar = min(restanteAEnviar, totalEspacioDisponible)
			recursoXciudad = restanteAEnviar // len(espacios_disponibles)

		banner()
		print(_('\nSe enviará {} a:').format(tipoDeBien[recurso].lower()))
		for city in toSend:
			print('  {}: {}'.format(ciudadesDestino[city]['name'], addDot(toSend[city])))

		print(_('\n¿Proceder? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			e.set()
			return
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set() #give main process control

	rutas = []
	for idCiudad in ciudadesDestino:
		ciudadD = ciudadesDestino[idCiudad]
		idIsla = ciudadD['islandId']
		faltante = toSend[idCiudad]
		for idCiudadOrigen in ciudadesOrigen:
			if faltante == 0:
				break
			ciudadO = ciudadesOrigen[idCiudadOrigen]
			recursoDisponible = ciudadO['disponible']
			for ruta in rutas:
				origen = ruta[0]
				rec = ruta[recurso + 3]
				if origen['id'] == idCiudadOrigen:
					recursoDisponible -= rec
			enviar = faltante if recursoDisponible > faltante else recursoDisponible
			disponible = ciudadD['disponible']
			if disponible < enviar:
				faltante = 0
				enviar = disponible
			else:
				faltante -= enviar

			if recurso == 1:
				ruta = (ciudadO, ciudadD, idIsla, 0, enviar, 0, 0, 0)
			elif recurso == 2:
				ruta = (ciudadO, ciudadD, idIsla, 0, 0, enviar, 0, 0)
			elif recurso == 3:
				ruta = (ciudadO, ciudadD, idIsla, 0, 0, 0, enviar, 0)
			else:
				ruta = (ciudadO, ciudadD, idIsla, 0, 0, 0, 0, enviar)
			rutas.append(ruta)

	info = _('\nRepartir recurso\n')
	for ruta in rutas:
		(ciudadO, ciudadD, idIsla, md, vn, mr, cr, az) = ruta
		rec = ruta[recurso + 3]
		info = info + '{} -> {}\n{}: {}\n'.format(ciudadO['cityName'], ciudadD['cityName'], tipoDeBien[recurso], addDot(rec))
	setInfoSignal(s, info)
	try:
		executeRoutes(s, rutas)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()
