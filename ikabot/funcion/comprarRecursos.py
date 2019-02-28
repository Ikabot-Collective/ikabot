#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from ikabot.helpers.gui import enter, banner
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.pedirInfo import getIdsDeCiudades, read
from ikabot.config import *

def asignarRecursoBuscado(s, ciudad, recurso):
	for pos, edificio in enumerate(ciudad['position']):
		if edificio['building'] == 'branchOffice':
			posicion = pos
			break
	data = {
	'cityId': ciudad['id'],
	'position': posicion,
	'view': 'branchOffice',
	'activeTab': 'bargain',
	'type': 9999999,
	'searchResource': recurso,
	'range': 9999999,
	'backgroundView' : 'city',
	'currentCityId': ciudad['id'],
	'templateView': 'branchOffice',
	'actionRequest': s.token(),
	'ajax': 1
	}
	rta = s.post(payloadPost=data)

def getStoreHtml(s, ciudad):
	url = 'view=branchOffice&cityId={}&position={}&currentCityId={}&backgroundView=city&actionRequest={}&ajax=1'.format(ciudad['id'], ciudad['pos'], ciudad['id'], s.token())
	data = s.post(url)
	json_data = json.loads(data, strict=False)
	return json_data[1][1][1]

def obtenerOfertas(s, ciudad):
	html = getStoreHtml(s, ciudad)
	hits = re.findall(r'short_text80\\">(.*?) *<br\/>(.*?)\\n *<\/td>\\n *<td>(\d+)<\/td>\\n *<td>(.*?)\/td>\\n *<td><img src=\\"skin\/resources\/icon_(\w+).png.*?href=\\"\?view=takeOffer&destinationCityId=(\d+)&oldView=branchOffice&activeTab=bargain&cityId=(\d+)&position=(\d+)&type=(\d+)&resource=(\d+)\\"', html)
	ofertas = []
	for hit in hits:
		oferta = {
		'ciudadDestino': hit[0],
		'jugadorAComprar' : hit[1],
		'bienesXminuto': hit[2],
		'cantidadDisponible': hit[3],
		'tipo': hit[4],
		'destinationCityId': hit[5],
		'cityId': hit[6],
		'position': hit[7],
		'type': hit[8],
		'resource': hit[9]
		}
		ofertas.append(oferta)
	return ofertas

def comprarRecursos(s):
	banner()

	ids = getIdsDeCiudades(s)[0]
	ciudades_comerciales = []
	for idCiudad in ids:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		esComercial = False
		for pos, edificio in enumerate(ciudad['position']):
			if edificio['building'] == 'branchOffice':
				ciudad['pos'] = pos
				html = getStoreHtml(s, ciudad)
				rangos = re.findall(r'<option.*?>(\d+)<\/option>', html)
				ciudad['rango'] = max(rangos)
				ciudades_comerciales.append(ciudad)
				break

	if len(ciudades_comerciales) == 0:
		print('No hay una Tienda contruida')
		enter()
		return

	ciudadOrigen = ciudades_comerciales[0] # por ahora solo uso la primera ciudad

	print('Qué tipo de recurso quiere comprar?')
	for indice, bien in enumerate(tipoDeBien):
		print('({:d}) {}'.format(indice+1, bien))
	recurso = read(min=1, max=5)

	print(ciudad['pos'])
	print(ciudad['rango'])
	enter()

	asignarRecursoBuscado(s, ciudadOrigen, recurso)


	data = {
	'action': 'transportOperations',
	'function': 'buyGoodsAtAnotherBranchOffice',
	'cityId': 99999,
	'destinationCityId': 999,
	'oldView': 'branchOffice',
	'position': 13,
	'avatar2Name': jugadorAComprar,
	'city2Name': ciudadDestino,
	'type': 444,
	'activeTab': 'bargain',
	'transportDisplayPrice': 0,
	'premiumTransporter': 0,
	'tradegood3Price': 10,
	'cargo_tradegood3': cargaTotal,
	'capacity': 5,
	'max_capacity': 5,
	'jetPropulsion': 0,
	'transporters': barcos,
	'backgroundView': 'city',
	'currentCityId': 99999,
	'templateView': 'takeOffer',
	'currentTab': 'bargain',
	'actionRequest': s.token(),
	'ajax': 1
	}
	rta = s.post(payloadPost=data)
