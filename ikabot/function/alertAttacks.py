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
from ikabot.function.vacationMode import activateVacationMode

t = gettext.translation('alertAttacks',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def alertAttacks(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		if checkTelegramData(s) is False:
			e.set()
			return

		banner()
		default = 20
		minutes = read(msg=_('How often should I search for attacks?(min:3, default: {:d}): ').format(default), min=3, empty=True)
		if minutes == '':
			minutes = default
		print(_('I will check for attacks every {:d} minutes').format(minutes))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI check for attacks every {:d} minutes\n').format(minutes)
	setInfoSignal(s, info)
	try:
		do_it(s, minutes)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def respondToAttack(s):
	# this allows the user to respond to an attack via telegram
	while True:
		time.sleep(60 * 3)
		responses = getUserResponse(s)
		for response in responses:
			# the response should be in the form of:
			# <pid>:<action number>
			rta = re.search(r'(\d+):?\s*(\d+)', response)
			if rta is None:
				continue

			pid = int(rta.group(1))
			action 	= int(rta.group(2))

			# if the pid doesn't match, we ignore it
			if pid != os.getpid():
				continue

			# currently just one action is supported
			if action == 1:
				# mv
				activateVacationMode(s)
			else:
				sendToBot(s, _('Invalid command: {:d}').format(action))

def do_it(s, minutes):
	# this thread lets the user react to an attack once the alert is sent
	t = threading.Thread(target=respondToAttack, args=(s,))
	t.start()

	knownAttacks = []
	while True:
		# get the militaryMovements
		html = s.get()
		idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest=REQUESTID&ajax=1'.format(idCiudad)
		posted = s.post(url)
		postdata = json.loads(posted, strict=False)
		militaryMovements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
		timeNow = int(postdata[0][1]['time'])

		currentAttacks = []
		for militaryMovement in [ mov for mov in militaryMovements if mov['isHostile'] ]:
			id = militaryMovement['event']['id']
			currentAttacks.append(id)
			# if we already alerted this, do nothing
			if id not in knownAttacks:
				knownAttacks.append(id)

				# get information about the attack
				missionText = militaryMovement['event']['missionText']
				origin = militaryMovement['origin']
				target = militaryMovement['target']
				amountTroops = militaryMovement['army']['amount']
				amountFleets = militaryMovement['fleet']['amount']
				timeLeft = int(militaryMovement['eventTime']) - timeNow

				# send alert
				msg  = _('-- ALERT --\n')
				msg += missionText + '\n'
				msg += _('from the city {} of {}\n').format(origin['name'], origin['avatarName'])
				msg += _('a {}\n').format(target['name'])
				msg += _('{} units\n').format(amountTroops)
				msg += _('{} fleet\n').format(amountFleets)
				msg += _('arrival in: {}\n').format(daysHoursMinutes(timeLeft))
				msg += _('If you want to put the account in vacation mode send:\n')
				msg += _('{:d}:1').format(os.getpid())
				sendToBot(s, msg)

		# remove old attacks from knownAttacks
		for id in list(knownAttacks):
			if id not in currentAttacks:
				knownAttacks.remove(id)

		time.sleep(minutes * 60)
