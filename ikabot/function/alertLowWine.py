#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import traceback
import gettext
from decimal import *
from ikabot.config import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import getIdsOfCities
from ikabot.helpers.varios import daysHoursMinutes
from ikabot.helpers.recursos import *
from ikabot.helpers.botComm import *


t = gettext.translation('alertLowWine',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

def alertLowWine(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		if botValido(s) is False:
			e.set()
			return
		banner()
		horas = read(msg=_('How many hours should be left until the wine runs out in a city so that it\'s alerted?'), min=1)
		print(_('It will be alerted when the wine runs out in less than {:d} hours in any city').format(horas))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI alert if the wine runs out in less than {:d} hours\n').format(horas)
	setInfoSignal(s, info)
	try:
		do_it(s, horas)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def do_it(s, horas):
	ids, ciudades = getIdsOfCities(s)
	while True:
		ids, ciudades_new = getIdsOfCities(s)
		if len(ciudades_new) != len(ciudades):
			ciudades = ciudades_new

		for city in ciudades:
			if 'avisado' not in ciudades[city]:
				ciudades[city]['avisado'] = False

		for city in ciudades:
			if ciudades[city]['tradegood'] == '1':
				continue

			id = str(ciudades[city]['id'])
			html = s.get(urlCiudad + id)
			consumoXhr = getConsumoDeVino(html)
			consumoXseg = Decimal(consumoXhr) / Decimal(3600)
			vinoDisp = getRecursosDisponibles(html, num=True)[1]
			if consumoXseg == 0:
				if ciudades[city]['avisado'] is False:
					msg = _('The city {} is not consuming wine!').format(ciudades[city]['name'])
					sendToBot(s, msg)
					ciudades[city]['avisado'] = True
				continue
			segsRestantes = Decimal(vinoDisp) / Decimal(consumoXseg)

			if segsRestantes < horas*60*60:
				if ciudades[city]['avisado'] is False:
					tiempoRestante = daysHoursMinutes(segsRestantes)
					msg = _('In {}, the wine will run out in {}').format(tiempoRestante, ciudades[city]['name'])
					sendToBot(s, msg)
					ciudades[city]['avisado'] = True
			else:
				ciudades[city]['avisado'] = False
		time.sleep(20*60)
