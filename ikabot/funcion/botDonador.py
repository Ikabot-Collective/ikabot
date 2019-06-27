#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.gui import *
from ikabot.helpers.process import forkear
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.recursos import getRecursosDisponibles

t = gettext.translation('botDonador', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def botDonador(s):
	banner()
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	ciudades_dict = {}
	bienes = {'1': _('(V)'), '2': '(M)', '3': '(C)', '4': _('(A)')}
	for idCiudad in idsCiudades:
		tradegood = ciudades[idCiudad]['tradegood']
		bien = bienes[tradegood]
		print(_('En la ciudad {} {}, ¿Desea donar al aserradero, al bien de cambio o a ninguno? [a/b/n]').format(ciudades[idCiudad]['name'], bien))
		rta = read(values=[_('a'), _('A'), _('b'), _('B'), 'n', 'N'])
		if rta.lower() == _('a'):
			tipo = 'resource'
		if rta.lower() == _('b'):
			tipo = 'tradegood'
		else:
			tipo = None
		ciudades_dict[idCiudad] = {'tipo': tipo}

	print(_('Se donará todos los días.'))
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = _('\nDono todos los días\n')
	setInfoSignal(s, info)
	try:
		do_it(s, idsCiudades, ciudades_dict)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s, idsCiudades, ciudades_dict):
	for idCiudad in idsCiudades:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		ciudades_dict[idCiudad]['isla'] = ciudad['islandId']
	while True:
		for idCiudad in idsCiudades:
			html = s.get(urlCiudad + idCiudad)
			madera = getRecursosDisponibles(html)[0]
			idIsla = ciudades_dict[idCiudad]['isla']
			tipo = ciudades_dict[idCiudad]['tipo']
			if tipo:
				s.post(payloadPost={'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': madera, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})
		msg = _('Doné automaticamente.')
		sendToBotDebug(msg, debugON_botDonador)
		time.sleep(24*60*60)
