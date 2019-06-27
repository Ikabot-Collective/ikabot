#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import math
import json
from decimal import *
from ikabot.helpers.varios import esperar
from ikabot.helpers.naval import *

def enviarBienes(s, idCiudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az, barcos):
	s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudadOrigen, 'ajax': '1'}) 
	s.post(payloadPost={'action': 'transportOperations', 'function': 'loadTransportersWithFreight', 'destinationCityId': idCiudadDestino, 'islandId': idIsla, 'oldView': '', 'position': '', 'avatar2Name': '', 'city2Name': '', 'type': '', 'activeTab': '', 'premiumTransporter': '0', 'minusPlusValue': '500', 'cargo_resource': md, 'cargo_tradegood1': vn, 'cargo_tradegood2': mr, 'cargo_tradegood3': cr, 'cargo_tradegood4': az, 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': barcos, 'backgroundView': 'city', 'currentCityId': idCiudadOrigen, 'templateView': 'transport', 'currentTab': 'tabSendTransporter', 'actionRequest': s.token(), 'ajax': '1'})

def planearViajes(s, rutas):
	for ruta in rutas:
		(ciudadOrigen, ciudadDestino, idIsla, md, vn, mr, cr, az) = ruta
		while (md + vn + mr + cr + az) > 0:
			barcosDisp = esperarLlegada(s)
			capacidad = barcosDisp * 500
			mdEnv = md if capacidad > md else capacidad
			capacidad -= mdEnv
			md -= mdEnv
			vnEnv = vn if capacidad > vn else capacidad
			capacidad -= vnEnv
			vn -= vnEnv
			mrEnv = mr if capacidad > mr else capacidad
			capacidad -= mrEnv
			mr -= mrEnv
			crEnv = cr if capacidad > cr else capacidad
			capacidad -= crEnv
			cr -= crEnv
			azEnv = az if capacidad > az else capacidad
			capacidad -= azEnv
			az -= azEnv
			cantEnviada = mdEnv + vnEnv + mrEnv + crEnv + azEnv
			barcos = int(math.ceil((Decimal(cantEnviada) / Decimal(500))))
			enviarBienes(s, ciudadOrigen['id'], ciudadDestino['id'], idIsla, mdEnv, vnEnv, mrEnv, crEnv, azEnv, barcos)

def obtenerMinimoTiempoDeEspera(s):
	html = s.get()
	idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
	url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
	posted = s.post(url)
	postdata = json.loads(posted, strict=False)
	militaryMovements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
	tiempoAhora = int(postdata[0][1]['time'])
	tiemposDeEspera = []
	for militaryMovement in [ mv for mv in militaryMovements if mv['isOwnArmyOrFleet'] ]:
		tiempoRestante = int(militaryMovement['eventTime']) - tiempoAhora
		tiemposDeEspera.append(tiempoRestante)
	if tiemposDeEspera:
		return min(tiemposDeEspera)
	else:
		return 0

def esperarLlegada(s):
	barcos = getBarcosDisponibles(s)
	while barcos == 0:
		minTiempoDeEspera = obtenerMinimoTiempoDeEspera(s)
		esperar( minTiempoDeEspera )
		barcos = getBarcosDisponibles(s)
	return barcos
