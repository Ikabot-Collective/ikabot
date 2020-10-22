#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import random
from decimal import *

getcontext().prec = 30

def addDot(num):
	"""Formats the number into a string and adds a '.' for every thousand (eg. 3000 -> 3.000)
	Parameters
	----------
	num : int
		integer number to format

	Returns
	-------
	number : str
		a string representing that number with added dots for every thousand
	"""
	return '{0:,}'.format(int(num)).replace(',','.')

def daysHoursMinutes(totalSeconds):
	"""Formats the total number of seconds into days hours minutes (eg. 321454 -> 3D 17H)
	Parameters
	----------
	totalSeconds : int
		total number of seconds

	Returns
	-------
	text : str
		formatted string (D H M)
	"""
	if totalSeconds == 0:
		return '0 s'
	dias = int(totalSeconds / Decimal(86400))
	totalSeconds -= dias * Decimal(86400)
	horas = int(totalSeconds / Decimal(3600))
	totalSeconds -= horas * Decimal(3600)
	minutos = int(totalSeconds / Decimal(60))
	texto = ''
	if dias > 0:
		texto = str(dias) + 'D '
	if horas > 0:
		texto = texto + str(horas) + 'H '
	if minutos > 0 and dias == 0:
		texto = texto + str(minutos) + 'M '
	return texto[:-1]

def wait(seconds, maxrandom = 0):
	"""This function will wait the provided number of seconds plus a random number of seconds between 0 and maxrandom
	Parameters
	-----------
	seconds : int
		the number of seconds to wait for
	maxrandom : int
		the maximum number of additional seconds to wait for
	"""
	if seconds <= 0:
		return
	randomTime = random.randint(0, maxrandom)
	ratio = (1 + 5 ** 0.5) / 2 - 1 # 0.6180339887498949
	comienzo = time.time()
	fin = comienzo + seconds
	restantes = seconds
	while restantes > 0:
		time.sleep(restantes * ratio)
		restantes = fin - time.time()
	time.sleep(randomTime)

def getCurrentCityId(session):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	"""
	html = session.get()
	return re.search(r'currentCityId:\s(\d+),', html).group(1)
