#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from decimal import *

ids = None
ciudades = None
urlCiudad = 'view=city&cityId='
getcontext().prec = 30

def getIdsDeCiudades(s):
	global ciudades
	global ids
	if ids is None or ciudades is None:
		html = s.get()
		ciudades = re.search(r'relatedCityData:\sJSON\.parse\(\'(.+?),\\"additionalInfo', html).group(1) + '}'
		ciudades = ciudades.replace('\\', '')
		ciudades = ciudades.replace('city_', '')
		ciudades = json.loads(ciudades, strict=False)
		ids = []
		for ciudad in ciudades:
			ids.append(ciudad)
	ids = sorted(ids)
	return (ids, ciudades)

def getIdsdeIslas(s):
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	idsIslas = set()
	for idCiudad in idsCiudades:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		idIsla = ciudad['islandId']
		idsIslas.add(idIsla)
	return list(idsIslas)
