#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import enter

t = gettext.translation('entrarDiariamente', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def entrarDiariamente(s):
	if botValido(s) is False:
		return
	print(_('Se entrará todos los días automaticamente.'))
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = _('\nEntro diariamente\n')
	setInfoSignal(s, info)
	try:
		do_it(s)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s):
	while True:
		s.get()
		time.sleep(24*60*60)
