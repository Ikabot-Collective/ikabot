#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from ikabot.helpers.botComm import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import enter

def entrarDiariamente(s):
	if botValido(s) is False:
		return
	print('Se entrará todos los días automaticamente.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nEntro diariamente\n'
	setInfoSignal(s, info)
	try:
		do_it(s)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s):
	while True:
		s.get()
		time.sleep(24*60*60)
