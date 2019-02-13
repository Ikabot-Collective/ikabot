#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planearViajes import planearViajes
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.process import forkear
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.recursos import *

def menuRutaComercial(s):
	rutas = []
	while True:

		banner()
		print('Ciudad de origen:')
		try:
			ciudadO = elegirCiudad(s)
		except KeyboardInterrupt:
			if rutas:
				print('¿Enviar viajes? [Y/n]')
				rta = read(values=['y', 'Y', 'n', 'N', ''])
				if rta.lower() != 'n':
					break
			return
		html = ciudadO['html']
		max = getRecursosDisponibles(html)
		total = list(map(int, max))

		banner()
		print('Ciudad de destino')
		ciudadD = elegirCiudad(s, ajenas=True)
		idIsla = ciudadD['islandId']

		if ciudadO['id'] == ciudadD['id']:
			continue

		if ciudadD['propia']:
			html = ciudadD['html']
			mad, vin, mar, cri, azu = getRecursosDisponibles(html, num=True)
			capacidad = getCapacidadDeAlmacenamiento(html)
			capacidad = int(capacidad)
			mad = capacidad - mad
			vin = capacidad - vin
			mar = capacidad - mar
			cri = capacidad - cri
			azu = capacidad - azu

		resto = total
		for ruta in rutas:
			(origen, destino, _, md, vn, mr, cr, az) = ruta
			if origen['id'] == ciudadO['id']:
				resto = (resto[0] - md, resto[1] - vn, resto[2] - mr, resto[3] - cr, resto[4] - az)
			if ciudadD['propia'] and destino['id'] == ciudadD['id']:
				mad = mad - md
				vin = vin - vn
				mar = mar - mr
				cri = cri - cr
				azu = azu - az

		banner()
		if ciudadD['propia']:
			msg = ''
			if resto[0] > mad:
				msg += '{} más de madera\n'.format(addPuntos(mad))
			if resto[1] > vin:
				msg += '{} más de vino\n'.format(addPuntos(vin))
			if resto[2] > mar:
				msg += '{} más de marmol\n'.format(addPuntos(mar))
			if resto[3] > cri:
				msg += '{} más de cristal\n'.format(addPuntos(cri))
			if resto[4] > azu:
				msg += '{} más de azufre\n'.format(addPuntos(azu))
			if msg:
				print('Solo puede almacenar:\n' + msg)
		print('Disponible:')
		print('Madera {} Vino {} Marmol {} Cristal {} Azufre {}'.format(addPuntos(resto[0]), addPuntos(resto[1]), addPuntos(resto[2]), addPuntos(resto[3]), addPuntos(resto[4])))
		print('Enviar:')
		try:
			md = pedirValor(' Madera:', resto[0])
			vn = pedirValor('   Vino:', resto[1])
			mr = pedirValor(' Marmol:', resto[2])
			cr = pedirValor('Cristal:', resto[3])
			az = pedirValor(' Azufre:', resto[4])
		except KeyboardInterrupt:
			continue
		if md + vn + mr + cr + az == 0:
			continue

		banner()
		print('Por enviar de {} a {}'.format(ciudadO['cityName'], ciudadD['cityName']))
		enviado = ''
		if md:
			enviado += 'Madera:{} '.format(addPuntos(md))
		if vn:
			enviado += 'Vino:{} '.format(addPuntos(vn))
		if mr:
			enviado += 'Marmol:{} '.format(addPuntos(mr))
		if cr:
			enviado += 'Cristal:{} '.format(addPuntos(cr))
		if az:
			enviado += 'Azufre:{}'.format(addPuntos(az))
		print(enviado)
		print('¿Proceder? [Y/n]')
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() != 'n':
			ruta = (ciudadO, ciudadD, idIsla, md, vn, mr, cr, az)
			rutas.append(ruta)
			print('¿Realizar otro envio? [y/N]')
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() != 'y':
				break

	forkear(s)
	if s.padre is True:
		return

	info = '\nRuta comercial\n'
	for ruta in rutas:
		(ciudadO, ciudadD, idIsla, md, vn, mr, cr, az) = ruta
		info = info + '{} -> {}\nMadera: {} Vino: {} Marmol: {} Cristal: {} Azufre: {}\n'.format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(md), addPuntos(vn), addPuntos(mr), addPuntos(cr), addPuntos(az))

	setInfoSignal(s, info)
	try:
		msg  = 'Comienzo a enviar recursos:\n'
		msg += info
		sendToBotDebug(msg, debugON_menuRutaComercial)

		planearViajes(s, rutas)

		msg  = 'Termino de enviar recursos:\n'
		msg += info
		sendToBotDebug(msg, debugON_menuRutaComercial)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()
