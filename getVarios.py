#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from decimal import *

getcontext().prec = 30

def getBarcosDisponibles(s):
	html = s.get()
	return int(re.search(r'GlobalMenu_freeTransporters">(\d+)<', html).group(1))

def getBarcosTotales(s):
	html = s.get()
	return int(re.search(r'maxTransporters">(\d+)<', html).group(1))

def getRecursosDisponibles(html, num=False):
	recursos = re.search(r'\\"resource\\":(\d+),\\"2\\":(\d+),\\"1\\":(\d+),\\"4\\":(\d+),\\"3\\":(\d+)}', html)
	if num:
		return [int(recursos.group(1)), int(recursos.group(3)), int(recursos.group(2)), int(recursos.group(5)), int(recursos.group(4))]
	else:
		return [recursos.group(1), recursos.group(3), recursos.group(2), recursos.group(5), recursos.group(4)]

def getCapacidadDeAlmacenamiento(html):
	return re.search(r'maxResources:\s*JSON\.parse\(\'{\\"resource\\":(\d+),', html).group(1)

def getConsumoDeVino(html):
	return int(re.search(r'GlobalMenu_WineConsumption"\s*class="rightText">\s*(\d*)\s', html).group(1))

def getProduccion(s, idCiudad):
	prod = s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudad, 'ajax': '1'}) 
	wood = Decimal(re.search(r'"resourceProduction":([\d|\.]+),', prod).group(1))
	good = Decimal(re.search(r'"tradegoodProduction":([\d|\.]+),', prod).group(1))
	typeGood = int(re.search(r'"producedTradegood":"([\d|\.]+)"', prod).group(1))
	return (wood, good, typeGood)
