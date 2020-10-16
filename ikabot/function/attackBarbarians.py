#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.getJson import getCity
from ikabot.helpers.signals import setInfoSignal

t = gettext.translation('attackBarbarians',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def choose_island(session):
	idsIslands = getIslandsIds(session)
	islands = []
	for idIsland in idsIslands:
		html = session.get(island_url + idIsland)
		island = getIsland(html)
		if island['barbarians']['destroyed'] == 0:
			islands.append(island)

	if len(islands) == 1:
		return islands[0]

	print(_('In which island do you want to attack the barbarians?'))
	print(_(' 0) Exit'))
	for i, island in enumerate(islands):
		pad = ' ' if i < 9 else ''
		print(_('{}{:d}) [{}:{}] {} ({}) : barbarians lv: {} ({})').format(pad, i+1, island['x'], island['y'], island['name'], materials_names[int(island['tradegood'])][0].upper(), island['barbarians']['level'], island['barbarians']['city']))

	index = read(min=0, max=len(islands))
	if index == 0:
		return None
	else:
		return islands[index-1]

def get_babarians_info(session, island):
	params = {"view": "barbarianVillage", "destinationIslandId": island['id'], "oldBackgroundView": "city", "cityWorldviewScale": "1", "islandId": island['id'], "backgroundView": "island", "currentIslandId": island['id'], "actionRequest": actionRequest, "ajax": "1"}
	resp = session.post(params=params)
	resp = json.loads(resp, strict=False)
	level = resp[2][1]['js_islandBarbarianLevel']['text']
	gold  = resp[2][1]['js_islandBarbarianResourcegold']['text']
	resources = [0] * len(materials_names)
	for i in range(len(materials_names)):
		if i == 0:
			resources[i] = resp[2][1]['js_islandBarbarianResourceresource']['text']
		else:
			resources[i] = resp[2][1]['js_islandBarbarianResourcetradegood{:d}'.format(i)]['text']
	info = {
		'level': level,
		'gold': gold,
		'resources': resources
	}
	return info

def attackBarbarians(session, event, stdin_fd):
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

		island = choose_island(session)
		if island is None:
			event.set()
			return

		info = get_babarians_info(session, island)


	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI attack the barbarians in [{}:{}] {:d} times\n').format(island['x'], island['y'], iterations)
	setInfoSignal(session, info)
	try:
		do_it(session, island, iterations)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def do_it(session, island, iterations):
	pass
