#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from helpers.botComm import *
from helpers.signals import setInfoSignal
from helpers.process import forkear
from helpers.gui import enter

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
		while True:
			s.get()
			time.sleep(24*60*60)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(s, msg)
		s.logout()
