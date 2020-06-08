#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from decimal import *

getcontext().prec = 30

def getRecursosDisponibles(html, num=False):
	recursos = re.search(r'\\"resource\\":(\d+),\\"2\\":(\d+),\\"1\\":(\d+),\\"4\\":(\d+),\\"3\\":(\d+)}', html)
	if num:
		return [int(recursos.group(1)), int(recursos.group(3)), int(recursos.group(2)), int(recursos.group(5)), int(recursos.group(4))]
	else:
		return [recursos.group(1), recursos.group(3), recursos.group(2), recursos.group(5), recursos.group(4)]

def getstorageCapacityDeAlmacenamiento(html):
	almacenamiento = re.search(r'maxResources:\s*JSON\.parse\(\'{\\"resource\\":(\d+),', html).group(1)
	return int(almacenamiento)

def getConsumoDeVino(html):
	rta = re.search(r'GlobalMenu_WineConsumption"\s*class="rightText">\s*(\d+)\s', html)
	if rta:
		return int(rta.group(1))
	return 0

def getProduccionPerSecond(s, idCiudad):
	prod = s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': 'REQUESTID', 'cityId': idCiudad, 'ajax': '1'})
	prod = json.loads(prod, strict=False)
	prod = prod[0][1]['headerData']
	wood = Decimal( prod['resourceProduction'] )
	good = Decimal( prod['tradegoodProduction'] )
	typeGood = int( prod['producedTradegood'] )
	return (wood, good, typeGood)
