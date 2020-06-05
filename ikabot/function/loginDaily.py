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
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def loginDaily(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		print(_('I will enter every day.'))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI enter every day\n')
	setInfoSignal(s, info)
	try:
		do_it(s)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def do_it(s):
	while True:
		(ids, cities) = getIdsOfCities(s)
		s.get('action=AvatarAction&function=giveDailyActivityBonus&dailyActivityBonusCitySelect={}&startPageShown=1&detectedDevice=1&autoLogin=on&cityId={}&activeTab=multiTab2&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(str(ids[0]), str(ids[0]), str(ids[0]), s.token()))
		wait(24*60*60, 1*60*60)
