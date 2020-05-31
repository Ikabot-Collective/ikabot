#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import banner
from ikabot.helpers.recursos import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.varios import addDot
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.planearViajes import planearViajes

t = gettext.translation('distributeResourcesEvenly',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def distributeResourcesEvenly(s,e,fd):
	sys.stdin = os.fdopen(fd) # give process access to terminal

	print(_('\n¿Proceder? [Y/n]'))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		e.set()
		return

	set_child_mode(s)
	e.set() #this is where we give back control to main process

	i = 0
	while True:
		i += 1
		time.sleep(3)
		fh = open('/tmp/ikabot/out.txt', 'a')
		fh.write('{:d}\n'.format(i))
		fh.close()
