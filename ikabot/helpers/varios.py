#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from decimal import *

getcontext().prec = 30

def addPuntos(num):
	return '{0:,}'.format(int(num)).replace(',','.')

def diasHorasMinutos(segundosTotales):
	dias = int(segundosTotales / Decimal(86400))
	segundosTotales -= dias * Decimal(86400)
	horas = int(segundosTotales / Decimal(3600))
	segundosTotales -= horas * Decimal(3600)
	minutos = int(segundosTotales / Decimal(60))
	texto = ''
	if dias > 0:
		texto = str(dias) + 'D '
	if horas > 0:
		texto = texto + str(horas) + 'H '
	if minutos > 0 and dias == 0:
		texto = texto + str(minutos) + 'M '
	return texto

def esperar(segundos):
	ratio = (1 + 5 ** 0.5) / 2 - 1
	comienzo = time.time()
	fin = comienzo + segundos
	restantes = segundos
	while restantes > 0:
		time.sleep(restantes * ratio)
		restantes = fin - time.time()
	return
