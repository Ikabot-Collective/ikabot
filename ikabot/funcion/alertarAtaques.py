#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
import re
import json
from ikabot.config import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import enter
from ikabot.helpers.varios import diasHorasMinutos
from ikabot.helpers.botComm import *

t = gettext.translation('alertarAtaques',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def alertarAtaques(s):
	if botValido(s) is False:
		return
	print(_('Se buscarán ataques cada 20 minutos.'))
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = _('\nEspero por ataques cada 20 minutos\n')
	setInfoSignal(s, info)
	try:
		do_it(s)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s):
	conocidos = []
	while True:
		html = s.get()
		idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
		posted = s.post(url)
		postdata = json.loads(posted, strict=False)
		militaryMovements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
		tiempoAhora = int(postdata[0][1]['time'])
		actuales = []
		for militaryMovement in militaryMovements:
			if militaryMovement['isHostile']:
				id = militaryMovement['event']['id']
				actuales.append(id)
				if id not in conocidos:
					conocidos.append(id)
					missionText = militaryMovement['event']['missionText']
					origin = militaryMovement['origin']
					target = militaryMovement['target']
					cantidadTropas = militaryMovement['army']['amount']
					cantidadFlotas = militaryMovement['fleet']['amount']
					tiempoFaltante = int(militaryMovement['eventTime']) - tiempoAhora
					msg  = _('-- ALERTA --\n')
					msg += missionText + '\n'
					msg += _('de la ciudad {} de {}\n').format(origin['name'], origin['avatarName'])
					msg += _('a {}\n').format(target['name'])
					msg += _('{} unidades\n').format(cantidadTropas)
					msg += _('{} flotas\n').format(cantidadFlotas)
					msg += _('llegada en: {}').format(diasHorasMinutos(tiempoFaltante))
					sendToBot(msg)
		for id in list(conocidos):
			if id not in actuales:
				conocidos.remove(id)
		time.sleep(20 * 60)
