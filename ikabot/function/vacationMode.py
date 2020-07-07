#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import sys
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCity

t = gettext.translation('vacationMode',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def activateVacationMode(session):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	"""
	html = session.get()
	city = getCity(html)

	data = {'action': 'Options', 'function': 'activateVacationMode', 'actionRequest': actionRequest, 'backgroundView': 'city', 'currentCityId': city['id'], 'templateView': 'options_umod_confirm'}
	session.post(params=data, ignoreExpire=True)

def vacationMode(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	try:
		banner()
		print(_('Activate vacation mode? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			event.set()
			return

		activateVacationMode(session)

		print(_('Vacation mode has been activated.'))
		enter()
		event.set()
		clear()
		exit()
	except KeyboardInterrupt:
		event.set()
		return
