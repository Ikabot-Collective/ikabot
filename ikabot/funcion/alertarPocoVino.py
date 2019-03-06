#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
import re
from decimal import *
from ikabot.config import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import forkear
from ikabot.helpers.gui import enter
from ikabot.helpers.pedirInfo import getIdsDeCiudades
from ikabot.helpers.varios import diasHorasMinutos
from ikabot.helpers.recursos import *
from ikabot.helpers.botComm import *

getcontext().prec = 30

def alertarPocoVino(s):
	if botValido(s) is False:
		return
	horas = read(msg='¿Cuántas horas deben quedar hasta que se acabe el vino en una ciudad para que es dé aviso?: ',min=1)
	print('Se avisará cuando el vino se acabe en {:d} horas en alguna ciudad.'.format(horas))
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nAviso si el vino se acaba en {:d} horas\n'.format(horas)
	setInfoSignal(s, info)
	try:
		do_it(s, horas)
	except:
		msg = 'Error en:\n{}\nCausa:\n{}'.format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s, horas):
	ids, ciudades = getIdsDeCiudades(s)
	for city in ciudades:
		ciudades[city]['avisado'] = False

	while True:
		for city in ciudades:
			if ciudades[city]['tradegood'] == '1':
				continue

			id = str(ciudades[city]['id'])
			html = s.get(urlCiudad + id)
			consumoXhr = getConsumoDeVino(html)
			consumoXseg = Decimal(consumoXhr) / Decimal(3600)
			max = getRecursosDisponibles(html)
			if consumoXseg == 0:
				if ciudades[city]['avisado'] is False:
					msg = 'La ciudad {} no esta consumiendo vino!'.format(ciudades[city]['name'])
					sendToBot(msg)
					ciudades[city]['avisado'] = True
				continue
			segsRestantes = Decimal(int(max[1])) / Decimal(consumoXseg)

			if segsRestantes < horas*60*60:
				if ciudades[city]['avisado'] is False:
					tiempoRestante = diasHorasMinutos(segsRestantes)
					msg = 'En {} se acabará el vino en {}'.format(tiempoRestante, ciudades[city]['name'])
					sendToBot(msg)
					ciudades[city]['avisado'] = True
			else:
				ciudades[city]['avisado'] = False
		time.sleep(20*60)
