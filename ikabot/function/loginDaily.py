#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
import sys
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.gui import enter
from ikabot.helpers.pedirInfo import getIdsOfCities
from ikabot.helpers.varios import wait

t = gettext.translation('loginDaily',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def loginDaily(session, event, stdin_fd):
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
		print(_('I will enter every day.'))
		enter()
	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI enter every day\n')
	setInfoSignal(session, info)
	try:
		do_it(session)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def do_it(session):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	"""
	while True:
		(ids, cities) = getIdsOfCities(session)
		cityId = ids[0]
		url = 'action=AvatarAction&function=giveDailyActivityBonus&dailyActivityBonusCitySelect={0}&startPageShown=1&detectedDevice=1&autoLogin=on&cityId={0}&activeTab=multiTab2&backgroundView=city&currentCityId={0}&actionRequest={1}&ajax=1'.format(cityId, actionRequest)
		session.post(url)
		wait(24*60*60, 1*60*60)
