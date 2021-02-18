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
                        languages=languages,
                        fallback=True)
_ = t.gettext

def alertAttacks(session, event, stdin_fd, predetermined_input):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	predetermined_input : multiprocessing.managers.SyncManager.list
	"""
	sys.stdin = os.fdopen(stdin_fd)
	config.predetermined_input = predetermined_input
	try:
		if checkTelegramData(session) is False:
			event.set()
			return

		banner()
		default = 20
		minutes = read(msg=_('How often should I search for attacks?(min:3, default: {:d}): ').format(default), min=3, empty=True)
		if minutes == '':
			minutes = default
		print(_('I will check for attacks every {:d} minutes').format(minutes))
		enter()
	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI check for attacks every {:d} minutes\n').format(minutes)
	setInfoSignal(session, info)
	try:
		do_it(session, minutes)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def respondToAttack(session):
	"""
	Parameters
	---------
	session : ikabot.web.session.Session
	"""

	# this allows the user to respond to an attack via telegram
	while True:
		time.sleep(60 * 3)
		responses = getUserResponse(session)
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
				activateVacationMode(session)
			else:
				sendToBot(session, _('Invalid command: {:d}').format(action))

def do_it(session, minutes):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	minutes : int
	"""

	# this thread lets the user react to an attack once the alert is sent
	thread = threading.Thread(target=respondToAttack, args=(session,))
	thread.start()

	knownAttacks = []
	while True:
		# get the militaryMovements
		html = session.get()
		city_id = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(city_id, actionRequest)
		movements_response = session.post(url)
		postdata = json.loads(movements_response, strict=False)
		militaryMovements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
		timeNow = int(postdata[0][1]['time'])

		currentAttacks = []
		for militaryMovement in [ mov for mov in militaryMovements if mov['isHostile'] ]:
			event_id = militaryMovement['event']['id']
			currentAttacks.append(event_id)
			# if we already alerted this, do nothing
			if event_id not in knownAttacks:
				knownAttacks.append(event_id)

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
				sendToBot(session, msg)

		# remove old attacks from knownAttacks
		for event_id in list(knownAttacks):
			if event_id not in currentAttacks:
				knownAttacks.remove(event_id)

		time.sleep(minutes * 60)
