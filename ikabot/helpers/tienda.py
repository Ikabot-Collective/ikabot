#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from ikabot.config import *
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.pedirInfo import getIdsDeCiudades

def getCiudadesComerciales(s):
	ids = getIdsDeCiudades(s)[0]
	ciudades_comerciales = []
	for idCiudad in ids:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		for pos, edificio in enumerate(ciudad['position']):
			if edificio['building'] == 'branchOffice':
				ciudad['pos'] = pos
				html = getStoreHtml(s, ciudad)
				rangos = re.findall(r'<option.*?>(\d+)</option>', html)
				ciudad['rango'] = int(rangos[-1])
				ciudades_comerciales.append(ciudad)
				break
	return ciudades_comerciales

def getStoreHtml(s, ciudad):
	url = 'view=branchOffice&cityId={}&position={:d}&currentCityId={}&backgroundView=city&actionRequest={}&ajax=1'.format(ciudad['id'], ciudad['pos'], ciudad['id'], s.token())
	data = s.post(url)
	json_data = json.loads(data, strict=False)
	return json_data[1][1][1]

def getCapacidadDeVenta(html):
	match = re.search(r'var\s*storageCapacity\s*=\s*(\d+);', html)
	if match:
		return int(match.group(1))
	else:
		return 0

def vendiendo(html):
	mad, vin, mar, cri, azu = re.findall(r'<input type="text" class="textfield"\s*size="\d+"\s*name=".*?"\s*id=".*?"\s*value="(\d+)"', html)
	return [int(mad), int(vin), int(mar), int(cri), int(azu)]
