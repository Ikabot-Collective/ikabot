#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
import re
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import enter
from ikabot.helpers.botComm import *

def alertarAtaques(s):
	if botValido(s) is False:
		return
	print('Se buscarán ataques cada 15 minutos.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nEspero por ataques cada 15 minutos\n'
	setInfoSignal(s, info)
	try:
		do_it(s)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(s, msg)
		s.logout()

def do_it(s):
	fueAvisado = False
	while True:
		html = s.get()
		idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
		posted = s.post(url)
		ataque = re.search(r'"military":{"link":.*?","cssclass":"normalalert"', posted)
		if ataque is not None and fueAvisado is False:
			msg = '¡Te están por atacar!'
			sendToBot(s, msg)
			fueAvisado = True
		elif ataque is None and fueAvisado is True:
			fueAvisado = False
		time.sleep(15*60)
