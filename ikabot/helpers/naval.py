#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def getAvailableShips(s):
	"""Function that returns the total number of free (available) ships
	Parameters
	----------
	s : Session
		Session object
	
	Returns
	-------
	ships : int
		number of currently available ships
	"""
	html = s.get()
	return int(re.search(r'GlobalMenu_freeTransporters">(\d+)<', html).group(1))

def getTotalShips(s):
	"""Function that returns the total number of ships, regardless of if they're available or not
	Parameters
	----------
	s : Session
		Session object
	
	Returns
	-------
	ships : int
		total number of ships the player has
	"""
	html = s.get()
	return int(re.search(r'maxTransporters">(\d+)<', html).group(1))
