#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def getAvailableShips(session):
	"""Function that returns the total number of free (available) ships
	Parameters
	----------
	session : ikabot.web.session.Session
		Session object

	Returns
	-------
	ships : int
		number of currently available ships
	"""
	html = session.get()
	return int(re.search(r'GlobalMenu_freeTransporters">(\d+)<', html).group(1))

def getTotalShips(session):
	"""Function that returns the total number of ships, regardless of if they're available or not
	Parameters
	----------
	session : ikabot.web.session.Session
		Session object

	Returns
	-------
	ships : int
		total number of ships the player has
	"""
	html = session.get()
	return int(re.search(r'maxTransporters">(\d+)<', html).group(1))
