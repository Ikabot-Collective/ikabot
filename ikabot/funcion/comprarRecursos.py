#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import math
import json
import gettext
import traceback
from decimal import *
from ikabot.helpers.process import forkear
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.gui import enter, banner
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.planearViajes import esperarLlegada
from ikabot.helpers.pedirInfo import getIdsDeCiudades, read
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.recursos import *

t = gettext.translation('comprarRecursos', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def asignarRecursoBuscado(s, ciudad):
	print(_('¿Qué recurso quiere comprar?'))
	for indice, bien in enumerate(tipoDeBien):
		print('({:d}) {}'.format(indice+1, bien))
	eleccion = read(min=1, max=5)
	recurso = eleccion - 1
	if recurso == 0:
		recurso = 'resource'
	data = {
	'cityId': ciudad['id'],
	'position': ciudad['pos'],
	'view': 'branchOffice',
	'activeTab': 'bargain',
	'type': 444,
	'searchResource': recurso,
	'range': ciudad['rango'],
	'backgroundView' : 'city',
	'currentCityId': ciudad['id'],
	'templateView': 'branchOffice',
	'currentTab': 'bargain',
	'actionRequest': s.token(),
	'ajax': 1
	}
	rta = s.post(payloadPost=data)
	return eleccion, recurso

def getStoreHtml(s, ciudad):
	url = 'view=branchOffice&cityId={}&position={:d}&currentCityId={}&backgroundView=city&actionRequest={}&ajax=1'.format(ciudad['id'], ciudad['pos'], ciudad['id'], s.token())
	data = s.post(url)
	json_data = json.loads(data, strict=False)
	return json_data[1][1][1]

def obtenerOfertas(s, ciudad):
	html = getStoreHtml(s, ciudad)
	hits = re.findall(r'short_text80">(.*?) *<br/>\((.*?)\)\s *</td>\s *<td>(\d+)</td>\s *<td>(.*?)/td>\s *<td><img src="skin/resources/icon_(\w+)\.png[\s\S]*?white-space:nowrap;">(\d+)\s[\s\S]*?href="\?view=takeOffer&destinationCityId=(\d+)&oldView=branchOffice&activeTab=bargain&cityId=(\d+)&position=(\d+)&type=(\d+)&resource=(\w+)"', html)
	ofertas = []
	for hit in hits:
		oferta = {
		'ciudadDestino': hit[0],
		'jugadorAComprar' : hit[1],
		'bienesXminuto': int(hit[2]),
		'cantidadDisponible': int(hit[3].replace(',', '').replace('<', '')),
		'tipo': hit[4],
		'precio': int(hit[5]),
		'destinationCityId': hit[6],
		'cityId': hit[7],
		'position': hit[8],
		'type': hit[9],
		'resource': hit[10]
		}
		ofertas.append(oferta)
	return ofertas

def calcularCosto(ofertas, cantidadAComprar):
	costoTotal = 0
	for oferta in ofertas:
		if cantidadAComprar == 0:
			break
		comprar = oferta['cantidadDisponible'] if oferta['cantidadDisponible'] < cantidadAComprar else cantidadAComprar
		cantidadAComprar -= comprar
		costoTotal += comprar * oferta['precio']
	return costoTotal

def getOro(s, ciudad):
	url = 'view=finances&backgroundView=city&currentCityId={}&templateView=finances&actionRequest={}&ajax=1'.format(ciudad['id'], s.token())
	data = s.post(url)
	json_data = json.loads(data, strict=False)
	oro = json_data[0][1]['headerData']['gold']
	return int(oro.split('.')[0])

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

def comprarRecursos(s):
	banner()

	ciudades_comerciales = getCiudadesComerciales(s)
	if len(ciudades_comerciales) == 0:
		print(_('No hay una Tienda contruida'))
		enter()
		return

	ciudad = ciudades_comerciales[0] # por ahora solo uso la primera ciudad

	numRecurso, recurso = asignarRecursoBuscado(s, ciudad)
	banner()

	ofertas = obtenerOfertas(s, ciudad)
	if len(ofertas) == 0:
		print(_('No se encontraron ofertas.'))
		return

	precio_total   = 0
	cantidad_total = 0
	for oferta in ofertas:
		cantidad = oferta['cantidadDisponible']
		unidad   = oferta['precio']
		costo    = cantidad * unidad
		print(_('cantidad :{}').format(addPuntos(cantidad)))
		print(_('precio   :{:d}').format(unidad))
		print(_('costo    :{}').format(addPuntos(costo)))
		print('')
		precio_total += costo
		cantidad_total += cantidad

	ocupado = getRecursosDisponibles(ciudad['html'], num=True)[numRecurso - 1]
	capacidad = getCapacidadDeAlmacenamiento(ciudad['html'], num=True)
	disponible = capacidad - ocupado

	print(_('Total disponible para comprar: {}, por {}').format(addPuntos(cantidad_total), addPuntos(precio_total)))
	if disponible < cantidad_total:
		print(_('Solo se puede comprar {} por falta de almacenamiento.').format(addPuntos(disponible)))
		cantidad_total = disponible
	print('')
	cantidadAComprar = read(msg=_('¿Cuánta cantidad comprar? '), min=0, max=cantidad_total)
	if cantidadAComprar == 0:
		return

	oro = getOro(s, ciudad)
	costoTotal = calcularCosto(ofertas, cantidadAComprar)

	print(_('\nOro actual : {}.\nCosto total: {}.\nOro final  : {}.'). format(addPuntos(oro), addPuntos(costoTotal), addPuntos(oro - costoTotal)))
	print(_('¿Proceder? [Y/n]'))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		return

	print(_('Se comprará {}').format(addPuntos(cantidadAComprar)))
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = _('\nCompro {} de {} para {}\n').format(addPuntos(cantidadAComprar), tipoDeBien[numRecurso - 1], ciudad['cityName'])
	setInfoSignal(s, info)
	try:
		do_it(s, ciudad, ofertas, cantidadAComprar)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def buy(s, ciudad, oferta, cantidad):
	barcos = int(math.ceil((Decimal(cantidad) / Decimal(500))))
	data_dict = {
	'action': 'transportOperations',
	'function': 'buyGoodsAtAnotherBranchOffice',
	'cityId': oferta['cityId'],
	'destinationCityId': oferta['destinationCityId'],
	'oldView': 'branchOffice',
	'position': ciudad['pos'],
	'avatar2Name': oferta['jugadorAComprar'],
	'city2Name': oferta['ciudadDestino'],
	'type': int(oferta['type']),
	'activeTab': 'bargain',
	'transportDisplayPrice': 0,
	'premiumTransporter': 0,
	'capacity': 5,
	'max_capacity': 5,
	'jetPropulsion': 0,
	'transporters': barcos,
	'backgroundView': 'city',
	'currentCityId': oferta['cityId'],
	'templateView': 'takeOffer',
	'currentTab': 'bargain',
	'actionRequest': s.token(),
	'ajax': 1
	}
	url = 'view=takeOffer&destinationCityId={}&oldView=branchOffice&activeTab=bargain&cityId={}&position={}&type={}&resource={}&backgroundView=city&currentCityId={}&templateView=branchOffice&actionRequest={}&ajax=1'.format(oferta['destinationCityId'], oferta['cityId'], oferta['position'], oferta['type'], oferta['resource'], oferta['cityId'], s.token())
	data = s.post(url)
	html = json.loads(data, strict=False)[1][1][1]
	hits = re.findall(r'"tradegood(\d)Price"\s*value="(\d+)', html)
	for hit in hits:
		data_dict['tradegood{}Price'.format(hit[0])] = int(hit[1])
		data_dict['cargo_tradegood{}'.format(hit[0])] = 0
	hit = re.search(r'"resourcePrice"\s*value="(\d+)', html)
	if hit:
		data_dict['resourcePrice'] = int(hit.group(1))
		data_dict['cargo_resource'] = 0
	resource = oferta['resource']
	if resource == 'resource':
		data_dict['cargo_resource'] = cantidad
	else:
		data_dict['cargo_tradegood{}'.format(resource)] = cantidad
	s.post(payloadPost=data_dict)
	msg = _('Compro {} a {} de {}').format(addPuntos(cantidad), oferta['ciudadDestino'], oferta['jugadorAComprar'])
	sendToBotDebug(msg, debugON_comprarRecursos)

def do_it(s, ciudad, ofertas, cantidadAComprar):
	while True:
		for oferta in ofertas:
			if cantidadAComprar == 0:
				return
			if oferta['cantidadDisponible'] == 0:
				continue
			barcosDisp = esperarLlegada(s)
			capacidad  = barcosDisp * 500
			comprable_max = capacidad if capacidad < cantidadAComprar else cantidadAComprar
			compra = comprable_max if oferta['cantidadDisponible'] > comprable_max else oferta['cantidadDisponible']
			cantidadAComprar -= compra
			oferta['cantidadDisponible'] -= compra
			buy(s, ciudad, oferta, compra)
			break # vuelvo a empezar desde el principio
