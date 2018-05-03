#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from helpers.botComm import *
from helpers.signals import *
from helpers.gui import *

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
		msg = 'Ya no se entrará todos los días.\n{}'.format(traceback.format_exc())
		sendToBot(s, msg)
		s.logout()
