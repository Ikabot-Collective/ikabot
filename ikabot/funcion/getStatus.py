#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.naval import *
from ikabot.helpers.recursos import *
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.pedirInfo import getIdsDeCiudades

getcontext().prec = 30

def getStatus(s):
	banner()
	tipoCiudad = [bcolors.ENDC, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]
	ids, ciudades = getIdsDeCiudades(s)
	print('Barcos {:d}/{:d}'.format(getBarcosDisponibles(s), getBarcosTotales(s)))
	for unId in ids:
		html = s.get(urlCiudad + unId)
		ciudad = getCiudad(html)
		(wood, good, typeGood) = getProduccion(s, unId)
		print('\033[1m' + tipoCiudad[int(typeGood)] + ciudad['cityName'] + tipoCiudad[0])
		max = getRecursosDisponibles(html)
		capacidadDeAlmacenamiento = getCapacidadDeAlmacenamiento(html)
		crecursos = []
		for i in range(0,5):
			if max[i] == capacidadDeAlmacenamiento:
				crecursos.append(bcolors.RED)
			else:
				crecursos.append(bcolors.ENDC)
		print('Almacenamiento:')
		print(addPuntos(capacidadDeAlmacenamiento))
		print('Recursos:')
		print('Madera {1}{2}{0} Vino {3}{4}{0} Marmol {5}{6}{0} Cristal {7}{8}{0} Azufre {9}{10}{0}'.format(bcolors.ENDC, crecursos[0], addPuntos(max[0]), crecursos[1], addPuntos(max[1]), crecursos[2], addPuntos(max[2]), crecursos[3], addPuntos(max[3]), crecursos[4], addPuntos(max[4])))
		consumoXhr = getConsumoDeVino(html)
		tipo = tipoDeBien[typeGood]
		print('Producción:')
		print('Madera:{} {}:{}'.format(addPuntos(wood*3600), tipo, addPuntos(good*3600)))
		if consumoXhr == 0:
			print('{}{}No se consume vino!{}'.format(bcolors.RED, bcolors.BOLD, bcolors.ENDC))
		elif typeGood == 1 and (good*3600) > consumoXhr:
			print('Hay vino para:\n∞')
		else:
			consumoXseg = Decimal(consumoXhr) / Decimal(3600)
			segsRestantes = Decimal(int(max[1])) / Decimal(consumoXseg)
			texto = diasHorasMinutos(segsRestantes)
			print('Hay vino para:\n{}'.format(texto))
		for edificio in ciudad['position']:
			if edificio['name'] == 'empty':
				continue
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
			print('lv:{}\t{}{}{}'.format(level, color, edificio['name'], bcolors.ENDC))
		enter()
		print('')

def getProduccion(s, idCiudad):
	prod = s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudad, 'ajax': '1'}) 
	wood = Decimal(re.search(r'"resourceProduction":([\d|\.]+),', prod).group(1))
	good = Decimal(re.search(r'"tradegoodProduction":([\d|\.]+),', prod).group(1))
	typeGood = int(re.search(r'"producedTradegood":"([\d|\.]+)"', prod).group(1))
	return (wood, good, typeGood)
