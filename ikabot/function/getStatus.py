#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import gettext
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.varios import *
from ikabot.helpers.recursos import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import getCiudad

t = gettext.translation('getStatus', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

def getStatus(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()
		tipoCiudad = [bcolors.ENDC, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]

		print(_('Barcos {:d}/{:d}').format(getAvailableShips(s), getTotalShips(s)))

		print(_('\n¿De qué ciudad quiere ver el estado?'))
		ciudad = chooseCity(s)
		banner()

		(wood, good, typeGood) = getProduccion(s, ciudad['id'])
		print('\033[1m' + tipoCiudad[int(typeGood)] + ciudad['cityName'] + tipoCiudad[0])
		max = ciudad['recursos']
		storageCapacityDeAlmacenamiento = ciudad['storageCapacity']
		crecursos = []
		for i in range(0,5):
			if max[i] == storageCapacityDeAlmacenamiento:
				crecursos.append(bcolors.RED)
			else:
				crecursos.append(bcolors.ENDC)
		print(_('Almacenamiento:'))
		print(addDot(storageCapacityDeAlmacenamiento))
		print(_('Recursos:'))
		print(_('Madera {1}{2}{0} Vino {3}{4}{0} Marmol {5}{6}{0} Cristal {7}{8}{0} Azufre {9}{10}{0}').format(bcolors.ENDC, crecursos[0], addDot(max[0]), crecursos[1], addDot(max[1]), crecursos[2], addDot(max[2]), crecursos[3], addDot(max[3]), crecursos[4], addDot(max[4])))
		consumoXhr = ciudad['consumo']
		tipo = tipoDeBien[typeGood]
		print(_('Producción:'))
		print(_('Madera:{} {}:{}').format(addDot(wood*3600), tipo, addDot(good*3600)))
		if consumoXhr == 0:
			print(_('{}{}No se consume vino!{}').format(bcolors.RED, bcolors.BOLD, bcolors.ENDC))
		elif typeGood == 1 and (good*3600) > consumoXhr:
			print(_('Hay vino para:\n∞'))
		else:
			consumoXseg = Decimal(consumoXhr) / Decimal(3600)
			segsRestantes = Decimal(max[1]) / Decimal(consumoXseg)
			texto = daysHoursMinutes(segsRestantes)
			print(_('Hay vino para:\n{}').format(texto))
		for edificio in [ edificio for edificio in ciudad['position'] if edificio['name'] != 'empty' ]:
			if edificio['isMaxLevel'] is True:
				color = bcolors.BLACK
			elif edificio['canUpgrade'] is True:
				color = bcolors.GREEN
			else:
				color = bcolors.RED
			level = edificio['level']
			if int(level) < 10:
				level = ' ' + level
			if edificio['isBusy'] is True:
				level = level + '+'
			print(_('lv:{}\t{}{}{}').format(level, color, edificio['name'], bcolors.ENDC))
		enter()
		print('')
		e.set()
	except KeyboardInterrupt:
		e.set()
		return

def getProduccion(s, idCiudad):
	prod = s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudad, 'ajax': '1'}) 
	wood = Decimal(re.search(r'"resourceProduction":([\d|\.]+),', prod).group(1))
	good = Decimal(re.search(r'"tradegoodProduction":([\d|\.]+),', prod).group(1))
	typeGood = int(re.search(r'"producedTradegood":"([\d|\.]+)"', prod).group(1))
	return (wood, good, typeGood)
