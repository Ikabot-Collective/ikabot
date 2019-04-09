#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter
from ikabot.helpers.varios import esperar
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.pedirInfo import getIdsdeIslas
from ikabot.helpers.getJson import getIsla
from ikabot.helpers.process import forkear

t = gettext.translation('buscarEspacios', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def buscarEspacios(s):
	if botValido(s) is False:
		return
	print(_('Se buscarán espacios nuevos cada hora.'))
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = _('\nBusco espacios nuevos en las islas cada 1 hora\n')
	setInfoSignal(s, info)
	try:
		do_it(s)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s):
	isla_ciudades = {}
	while True:
		idIslas = getIdsdeIslas(s)
		for idIsla in idIslas:
			html = s.get(urlIsla + idIsla)
			isla = getIsla(html)
			ciudades = [ciudad for ciudad in isla['cities'] if ciudad['type'] != 'empty']

			if idIsla in isla_ciudades:
				ciudadesAntes = isla_ciudades[idIsla]

				# alguien desaparecio
				for cityAntes in ciudadesAntes:
					for ciudad in ciudades:
						if ciudad['id'] == cityAntes['id']:
							break
					else:
						msg = _('la ciudad {} del jugador {} desapareció en {} {}:{} {}').format(cityAntes['name'], cityAntes['Name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
						sendToBot(msg)

				# alguien fundo
				for ciudad in ciudades:
					for cityAntes in ciudadesAntes:
						if ciudad['id'] == cityAntes['id']:
							break
					else:
						msg = _('{} fundó {} en {} {}:{} {}').format(ciudad['Name'], ciudad['name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
						sendToBot(msg)

			isla_ciudades[idIsla] = ciudades.copy()
		esperar(1*60*60)
