#! /usr/bin/env python3
# -*- coding: utf-8 -*-

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
	return (dias, horas, minutos)
