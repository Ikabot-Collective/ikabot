#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import time
import json
import traceback
import threading
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter
from ikabot.helpers.process import forkear
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import diasHorasMinutos
from ikabot.funcion.modoVacaciones import activarModoVacaciones

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

def respondToAttack(s):
	while True:
		time.sleep(60 * 3)
		responses = getUserResponse()
		for response in responses:
			rta = re.search(r'(\d+):?\s*(\d+)', response)
			if rta:
				obj = int(rta.group(1))
				if obj != os.getpid():
					continue
				accion 	= int(rta.group(2))
			else:
				continue
			s.padre = True
			forkear(s)
			if s.padre is True:
				s.padre = False
				continue
			else:
				if accion == 1:
					# mv
					activarModoVacaciones(s)
				else:
					sendToBot(_('Comando inválido: {:d}').format(accion))
				s.logout()
				exit()

def do_it(s):
	conocidos = []
	t = threading.Thread(target=respondToAttack, args=(s,))
	t.start()
	while True:
		html = s.get()
		idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
		posted = s.post(url)
		postdata = json.loads(posted, strict=False)
		militaryMovements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
		tiempoAhora = int(postdata[0][1]['time'])
		actuales = []
		for militaryMovement in [ mov for mov in militaryMovements if mov['isHostile'] ]:
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
				msg += _('llegada en: {}\n').format(diasHorasMinutos(tiempoFaltante))
				msg += _('Si quiere poner la cuenta en modo vacaciones envíe:\n')
				msg += _('{:d}:1').format(os.getpid())
				sendToBot(msg)

		for id in list(conocidos):
			if id not in actuales:
				conocidos.remove(id)
		time.sleep(20 * 60)
