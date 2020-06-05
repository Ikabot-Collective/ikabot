#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import time
import json
import traceback
import threading
import sys
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import daysHoursMinutes
from ikabot.function.vacationMode import activarvacationMode

t = gettext.translation('alertAttacks',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def alertAttacks(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		if botValido(s) is False:
			e.set()
			return

		banner()
		minutos = read(msg=_('How often should I search for attacks?(min:3, default: 20): '), min=3, empty=True)
		if minutos == '':
			minutos = 20
		print(_('I will check for attacks every {} minutes').format(minutos))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI check for attacks every {} minutes\n').format(minutos)
	setInfoSignal(s, info)
	try:
		do_it(s, minutos)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def respondToAttack(s):
	while True:
		time.sleep(60 * 3)
		responses = getUserResponse(s)
		for response in responses:
			rta = re.search(r'(\d+):?\s*(\d+)', response)
			if rta:
				obj = int(rta.group(1))
				if obj != os.getpid():
					continue
				accion 	= int(rta.group(2))
			else:
				continue

			if accion == 1:
				# mv
				activarvacationMode(s)
			else:
				sendToBot(s, _('Invalid command: {:d}').format(accion))

def do_it(s, minutos):
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
				msg  = _('-- ALERT --\n')
				msg += missionText + '\n'
				msg += _('from the city {} of {}\n').format(origin['name'], origin['avatarName'])
				msg += _('a {}\n').format(target['name'])
				msg += _('{} units\n').format(cantidadTropas)
				msg += _('{} fleet\n').format(cantidadFlotas)
				msg += _('arrival in: {}\n').format(daysHoursMinutes(tiempoFaltante))
				msg += _('If you want to put the account in vacation mode send:\n')
				msg += _('{:d}:1').format(os.getpid())
				sendToBot(s, msg)

		for id in list(conocidos):
			if id not in actuales:
				conocidos.remove(id)
		time.sleep(minutos * 60)
