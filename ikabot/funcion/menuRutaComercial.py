#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planearViajes import planearViajes
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.process import forkear
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.recursos import *


def menuRutaComercial(s):
	t = gettext.translation('menuRutaComercial', 
	                        localedir, 
	                        languages=idiomas,
	                        fallback=True)
	_ = t.gettext
	rutas = []
	while True:

		banner()
		print(_('Ciudad de origen:'))
		try:
			ciudadO = elegirCiudad(s)
		except KeyboardInterrupt:
			if rutas:
				print(_('¿Enviar viajes? [Y/n]'))
				rta = read(values=['y', 'Y', 'n', 'N', ''])
				if rta.lower() != 'n':
					break
			return
		html = ciudadO['html']
		max = getRecursosDisponibles(html)
		total = list(map(int, max))

		banner()
		print(_('Ciudad de destino'))
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
			(origen, destino, __, md, vn, mr, cr, az) = ruta
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
				msg += _('{} más de madera\n').format(addPuntos(mad))
			if resto[1] > vin:
				msg += _('{} más de vino\n').format(addPuntos(vin))
			if resto[2] > mar:
				msg += _('{} más de marmol\n').format(addPuntos(mar))
			if resto[3] > cri:
				msg += _('{} más de cristal\n').format(addPuntos(cri))
			if resto[4] > azu:
				msg += _('{} más de azufre\n').format(addPuntos(azu))
			if msg:
				print(_('Solo puede almacenar:\n{}').format(msg))
		print(_('Disponible:'))
		print(_('Madera {} Vino {} Marmol {} Cristal {} Azufre {}').format(addPuntos(resto[0]), addPuntos(resto[1]), addPuntos(resto[2]), addPuntos(resto[3]), addPuntos(resto[4])))
		print(_('Enviar:'))
		try:
			md = pedirValor(_(' Madera:'), resto[0])
			vn = pedirValor(_('   Vino:'), resto[1])
			mr = pedirValor(_(' Marmol:'), resto[2])
			cr = pedirValor(_('Cristal:'), resto[3])
			az = pedirValor(_(' Azufre:'), resto[4])
		except KeyboardInterrupt:
			continue
		if md + vn + mr + cr + az == 0:
			continue

		banner()
		print(_('Por enviar de {} a {}').format(ciudadO['cityName'], ciudadD['cityName']))
		enviado = ''
		if md:
			enviado += _('Madera:{} ').format(addPuntos(md))
		if vn:
			enviado += _('Vino:{} ').format(addPuntos(vn))
		if mr:
			enviado += _('Marmol:{} ').format(addPuntos(mr))
		if cr:
			enviado += _('Cristal:{} ').format(addPuntos(cr))
		if az:
			enviado += _('Azufre:{}').format(addPuntos(az))
		print(enviado)
		print(_('¿Proceder? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() != 'n':
			ruta = (ciudadO, ciudadD, idIsla, md, vn, mr, cr, az)
			rutas.append(ruta)
			print(_('¿Realizar otro envio? [y/N]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() != 'y':
				break

	forkear(s)
	if s.padre is True:
		return

	info = _('\nRuta comercial\n')
	for ruta in rutas:
		(ciudadO, ciudadD, idIsla, md, vn, mr, cr, az) = ruta
		info = info + _('{} -> {}\nMadera: {} Vino: {} Marmol: {} Cristal: {} Azufre: {}\n').format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(md), addPuntos(vn), addPuntos(mr), addPuntos(cr), addPuntos(az))

	setInfoSignal(s, info)
	try:
		msg  = _('Comienzo a enviar recursos:\n')
		msg += info
		sendToBotDebug(msg, debugON_menuRutaComercial)

		planearViajes(s, rutas)

		msg  = _('Termino de enviar recursos:\n')
		msg += info
		sendToBotDebug(msg, debugON_menuRutaComercial)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()
