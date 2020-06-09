#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from ikabot.helpers.recursos import *

def borrar(texto, ocurrencias):
	for ocurrencia in ocurrencias:
		texto = texto.replace(ocurrencia, '')
	return texto

def getCiudadanosDisponibles(html):
	ciudadanosDisp = re.search(r'js_GlobalMenu_citizens">(.*?)</span>', html).group(1)
	return int(ciudadanosDisp.replace(',', '').replace('.', ''))

def enVenta(html):
	rta = re.search(r'branchOfficeResources: JSON\.parse\(\'{\\"resource\\":\\"(\d+)\\",\\"1\\":\\"(\d+)\\",\\"2\\":\\"(\d+)\\",\\"3\\":\\"(\d+)\\",\\"4\\":\\"(\d+)\\"}\'\)', html)
	if rta:
		return [ int(rta.group(1)), int(rta.group(2)), int(rta.group(3)), int(rta.group(4)), int(rta.group(5))]
	else:
		return [0, 0, 0, 0, 0]

def getIsland(html):
	isla = re.search(r'\[\["updateBackgroundData",([\s\S]*?),"specialServerBadges', html).group(1) + '}'

	isla = isla.replace('buildplace', 'empty')
	isla = isla.replace('xCoord', 'x')
	isla = isla.replace('yCoord', 'y')
	isla = isla.replace(',"owner', ',"')
	isla = isla.replace(',"tradegoodLevel',',"goodLv')
	isla = isla.replace(',"tradegood', ',"good')
	isla = isla.replace(',"resourceLevel', ',"woodLv')
	isla = isla.replace(',"wonderLevel', ',"wonderLv')
	isla = isla.replace('avatarScores', 'scores')

	remove = []

	sub = re.search(r',"type":\d', isla).group()
	remove.append(sub)

	quitar = re.search(r'(,"barbarians[\s\S]*?),"scores"', isla).group(1) #to remove

	remove.append(quitar) #to remove
	remove.append(',"goodTarget":"tradegood"')
	remove.append(',"name":"Building ground"')
	remove.append(',"name":"Terreno"')
	remove.append(',"actions":[]') #to remove
	remove.append('"id":-1,')
	remove.append(',"level":0,"viewAble":1')
	remove.append(',"empty_type":"normal"')
	remove.append(',"empty_type":"premium"')
	remove.append(',"hasTreaties":0')
	remove.append(',"hasTreaties":1')
	remove.append(',"infestedByPlague":false')
	remove.append(',"infestedByPlague":true')
	remove.append(',"viewAble":0')
	remove.append(',"viewAble":1')
	remove.append(',"viewAble":2')
	isla = borrar(isla, remove)

	# {"id":idIsla,"name":nombreIsla,"x":,"y":,"good":numeroBien,"woodLv":,"goodLv":,"wonder":numeroWonder, "wonderName": "nombreDelMilagro","wonderLv":"5","cities":[{"type":"city","name":cityName,"id":cityId,"level":lvIntendencia,"Id":playerId,"Name":playerName,"AllyId":,"AllyTag":,"state":"vacation"},...}}
	isla = json.loads(isla, strict=False)
	tipo = re.search(r'"tradegood":"(\d)"', html).group(1)
	isla['tipo'] = tipo
	return isla

def getCity(html):

	ciudad = re.search(r'"updateBackgroundData",\s?([\s\S]*?)\],\["updateTemplateData"', html).group(1)
	ciudad = json.loads(ciudad, strict=False)

	ciudad['Id'] = ciudad.pop('ownerId')
	ciudad['Name'] = ciudad.pop('ownerName')
	ciudad['x'] = ciudad.pop('islandXCoord')
	ciudad['y'] = ciudad.pop('islandYCoord')
	ciudad['cityName'] = ciudad['name']

	i = 0
	for position in ciudad['position']:
		position['position'] = i
		i += 1
		if 'level' in position:
			position['level'] = int(position['level'])
		position['isBusy'] = False
		if 'constructionSite' in position['building']:
			position['isBusy'] = True
			position['building'] = position['building'][:-17]
		elif 'buildingGround ' in position['building']:
			position['name'] = 'empty'
			position['type'] = position['building'].split(' ')[-1]
			position['building'] = 'empty'

	ciudad['id'] = str(ciudad['id'])
	ciudad['propia'] = True
	ciudad['recursos'] = getRecursosDisponibles(html, num=True)
	ciudad['storageCapacity'] = getstorageCapacityDeAlmacenamiento(html)
	ciudad['ciudadanosDisp'] = getCiudadanosDisponibles(html)
	ciudad['consumo'] = getConsumoDeVino(html)
	ciudad['enventa'] = enVenta(html)
	ciudad['freeSpaceForResources'] = []
	for i in range(5):
		ciudad['freeSpaceForResources'].append( ciudad['storageCapacity'] - ciudad['recursos'][i] - ciudad['enventa'][i] )

	return ciudad
