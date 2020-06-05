#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planearViajes import executeRoutes
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.varios import addDot
from ikabot.helpers.recursos import *


def sendResources(s,e,fd):
	sys.stdin = os.fdopen(fd)
	t = gettext.translation('sendResources', 
	                        localedir, 
	                        languages=idiomas,
	                        fallback=True)
	_ = t.gettext
	try:
		rutas = []
		while True:

			banner()
			print(_('Origin city:'))
			try:
				ciudadO = chooseCity(s)
			except KeyboardInterrupt:
				if rutas:
					print(_('Send shipment? [Y/n]'))
					rta = read(values=['y', 'Y', 'n', 'N', ''])
					if rta.lower() != 'n':
						break
				e.set()
				return

			banner()
			print(_('Destination city'))
			ciudadD = chooseCity(s, foreign=True)
			idIsla = ciudadD['islandId']

			if ciudadO['id'] == ciudadD['id']:
				continue

			if ciudadD['propia']:
				mad = ciudadD['freeSpaceForResources'][0]
				vin = ciudadD['freeSpaceForResources'][1]
				mar = ciudadD['freeSpaceForResources'][2]
				cri = ciudadD['freeSpaceForResources'][3]
				azu = ciudadD['freeSpaceForResources'][4]

			resto = ciudadO['recursos']
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
					msg += _('{} more wood\n').format(addDot(mad if mad > 0 else 0))
				if resto[1] > vin:
					msg += _('{} more wine\n').format(addDot(vin if vin > 0 else 0))
				if resto[2] > mar:
					msg += _('{} more marble\n').format(addDot(mar if mar > 0 else 0))
				if resto[3] > cri:
					msg += _('{} more cristal\n').format(addDot(cri if cri > 0 else 0))
				if resto[4] > azu:
					msg += _('{} more sulfur\n').format(addDot(azu if azu > 0 else 0))
				if msg:
					print(_('You can store just:\n{}').format(msg))
			print(_('Available:'))
			print(_('Wood {} Wine {} Marbel {} Cristal {} Sulfur {}').format(addDot(resto[0]), addDot(resto[1]), addDot(resto[2]), addDot(resto[3]), addDot(resto[4])))
			print(_('Send:'))
			try:
				md = askForValue(_('   Wood:'), resto[0])
				vn = askForValue(_('   Wine:'), resto[1])
				mr = askForValue(_(' Marbel:'), resto[2])
				cr = askForValue(_('Cristal:'), resto[3])
				az = askForValue(_(' Sulfur:'), resto[4])
			except KeyboardInterrupt:
				continue
			if md + vn + mr + cr + az == 0:
				continue

			banner()
			print(_('About to send from {} to {}').format(ciudadO['cityName'], ciudadD['cityName']))
			enviado = ''
			if md:
				enviado += _('Wood:{} ').format(addDot(md))
			if vn:
				enviado += _('Wine:{} ').format(addDot(vn))
			if mr:
				enviado += _('Marble:{} ').format(addDot(mr))
			if cr:
				enviado += _('Cristal:{} ').format(addDot(cr))
			if az:
				enviado += _('Sulfur:{}').format(addDot(az))
			print(enviado)
			print(_('Proceed? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() != 'n':
				ruta = (ciudadO, ciudadD, idIsla, md, vn, mr, cr, az)
				rutas.append(ruta)
				print(_('Create another shipment? [y/N]'))
				rta = read(values=['y', 'Y', 'n', 'N', ''])
				if rta.lower() != 'y':
					break
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nSend resources\n')
	for ruta in rutas:
		(ciudadO, ciudadD, idIsla, md, vn, mr, cr, az) = ruta
		info = info + _('Wood: {} Wine: {} Marble: {} Cristal: {} Sulfur: {}\n').format(ciudadO['cityName'], ciudadD['cityName'], addDot(md), addDot(vn), addDot(mr), addDot(cr), addDot(az))

	setInfoSignal(s, info)
	try:
		msg  = _('I start to send the resources:\n')
		msg += info
		sendToBotDebug(s, msg, debugON_sendResources)

		executeRoutes(s, rutas)

		msg  = _('I finish sendind the resources:\n')
		msg += info
		sendToBotDebug(s, msg, debugON_sendResources)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()
