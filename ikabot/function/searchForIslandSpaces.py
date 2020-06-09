#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
import sys
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import enter, enter
from ikabot.helpers.varios import wait
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.pedirInfo import getIslandsIds
from ikabot.helpers.getJson import getIsland
from ikabot.helpers.process import set_child_mode

t = gettext.translation('searchForIslandSpaces', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def searchForIslandSpaces(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		if checkTelegramData(s) is False:
			e.set()
			return
		banner()
		print(_('I will search for new spaces each hour.'))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI search for new spaces each hour\n')
	setInfoSignal(s, info)
	try:
		do_it(s)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def do_it(s):
	# this dict will contain all the cities from each island
	# as they where in last scan
	cities_before_per_island = {}

	while True:
		# this is done inside the loop because the user may colonize in a new island
		islandsIds = getIslandsIds(s)
		for islandId in islandsIds:
			html = s.get(urlIsla + islandId)
			island = getIsland(html)
			# cities in the current island
			cities_now = [city_space for city_space in island['cities'] if city_space['type'] != 'empty'] #loads the islands non empty cities into ciudades

			# if we haven't scaned this island before,
			# save it and do nothing
			if islandId not in cities_before_per_island:
				cities_before_per_island[islandId] = cities_now.copy()
			else:
				cities_before = cities_before_per_island[islandId]

				# someone disappeared
				for city_before in cities_before:
					if city_before['id'] not in [ city_now['id'] for city_now in cities_now ]:
						# we didn't find the city_before in the cities_now
						msg = _('the city {} of the player {} disappeared in {} {}:{} {}').format(city_before['name'], city_before['Name'], materials_names[int(island['good'])], island['x'], island['y'], island['name'])
						sendToBot(s, msg)

				# someone colonised
				for city_now in cities_now:
					if city_now['id'] not in [ city_before['id'] for city_before in cities_before ]:
						# we didn't find the city_now in the cities_before
						msg = _('{} founded {} in {} {}:{} {}').format(city_now['Name'], city_now['name'], materials_names[int(island['good'])], island['x'], island['y'], island['name'])
						sendToBot(s, msg)

		wait(1*60*60)
