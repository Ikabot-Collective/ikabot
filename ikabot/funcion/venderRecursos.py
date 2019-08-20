#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import math
import gettext
import traceback
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.tienda import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import forkear
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.planearViajes import esperarLlegada

t = gettext.translation('venderRecursos', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def elegirCiudadComercial(ciudades_comerciales):
	print(_('¿En cuál ciudad quiere vender recursos?\n'))
	for i, ciudad in enumerate(ciudades_comerciales):
		print('({:d}) {}'.format(i + 1, ciudad['name']))
	ind = read(min=1, max=len(ciudades_comerciales))
	return ciudades_comerciales[ind - 1]

def venderRecursos(s):
	banner()

	ciudades_comerciales = getCiudadesComerciales(s)
	if len(ciudades_comerciales) == 0:
		print(_('No hay una Tienda contruida'))
		enter()
		return

	if len(ciudades_comerciales) == 1:
		ciudad = ciudades_comerciales[0]
	else:
		ciudad = elegirCiudadComercial(ciudades_comerciales)
		banner()

	print(_('¿Qué recurso quiere vender?'))
	for indice, bien in enumerate(tipoDeBien):
		print('({:d}) {}'.format(indice+1, bien))
	eleccion = read(min=1, max=len(tipoDeBien))
	recurso = eleccion - 1
	banner()

	data = {'cityId': ciudad['id'], 'position': ciudad['pos'], 'view': 'branchOffice', 'activeTab': 'bargain', 'type': '333', 'searchResource': str(recurso), 'range': ciudad['rango'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'branchOffice', 'currentTab': 'bargain', 'actionRequest': s.token(), 'ajax': '1'}
	resp = s.post(payloadPost=data)
	html = json.loads(resp, strict=False)[1][1][1]
	matches = re.findall(r'<td class=".*?">(\S*)\s*<br/>\((.*?)\)\s*</td>\s*<td>(.*?)</td>\s*<td><img src=".*?"\s*alt=".*?"\s*title=".*?"/></td>\s*<td style="white-space:nowrap;">(\d+)\s*<img src=".*?"\s*class=".*?"/>.*?</td>\s*<td>(\d+)</td>\s*<td><a onclick="ajaxHandlerCall\(this\.href\);return false;"\s*href="\?view=takeOffer&destinationCityId=(\d+)&', html)

	max_venta = 0
	profit    = 0
	for match in matches:
		city, user, cant, precio, dist, idDestino = match
		cantidad = cant.replace(',', '').replace('.', '')
		cantidad = int(cantidad)
		max_venta += cantidad
		profit += cantidad * int(precio)

	disp_venta = ciudad['recursos'][recurso]
	vender = disp_venta if disp_venta < max_venta else max_venta

	print(_('\n¿Cuánto quiere vender? [max = {}]').format(addPuntos(vender)))
	vender = read(min=0, max=vender)

	faltaVender = vender
	profit    = 0
	for match in matches:
		city, user, cant, precio, dist, idDestino = match
		cantidad = cant.replace(',', '').replace('.', '')
		cantidad = int(cantidad)
		compra = cantidad if cantidad < faltaVender else faltaVender
		faltaVender -= compra
		profit += compra * int(precio)
	print(_('\n¿Vender {} de {} por un total de {}? [Y/n]').format(addPuntos(vender), tipoDeBien[recurso], addPuntos(profit)))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		return

	forkear(s)
	if s.padre is True:
		return

	info = _('\nVendo {} de {} en {}\n').format(addPuntos(vender), tipoDeBien[recurso], ciudad['name'])
	setInfoSignal(s, info)
	try:
		do_it(s, vender,  matches, recurso, ciudad)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s, porVender, ofertas, recurso, ciudad):
	sendToBot('quiero vender: {}'.format(addPuntos(porVender)))
	for oferta in ofertas:
		city, user, cant, precio, dist, idDestino = oferta
		quiereComprar = cant.replace(',', '').replace('.', '')
		quiereComprar = int(quiereComprar)
		sendToBot('{} quiere comprar {}'.format(city, addPuntos(quiereComprar)))
		while True:
			barcos_disponibles = esperarLlegada(s)
			sendToBot('{:d} barcos_disponibles'.format(barcos_disponibles))
			cant_venta = quiereComprar if quiereComprar < porVender else porVender
			barcos_necesarios = int(math.ceil((Decimal(cant_venta) / Decimal(500))))
			barcos_usados = barcos_disponibles if barcos_disponibles < barcos_necesarios else barcos_necesarios
			if barcos_necesarios > barcos_usados:
				cant_venta = barcos_usados * 500
			porVender -= cant_venta
			quiereComprar -= cant_venta

			data = {'action': 'transportOperations', 'function': 'sellGoodsAtAnotherBranchOffice', 'cityId': ciudad['id'], 'destinationCityId': idDestino, 'oldView': 'branchOffice', 'position': ciudad['pos'], 'avatar2Name': user, 'city2Name': city, 'type': '333', 'activeTab': 'bargain', 'transportDisplayPrice': '0', 'premiumTransporter': '0', 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': str(barcos_usados), 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'takeOffer', 'currentTab': 'bargain', 'actionRequest': s.token(), 'ajax': '1'}
			if recurso == 0:
				data['resource'] = str(precio)
				data['resourcePrice'] = str(cant_venta)
			else:
				data['tradegood{:d}Price'.format(recurso)] = str(precio)
				data['cargo_tradegood{:d}'.format(recurso)] = str(cant_venta)
			msg = 'vendo {} a {} ({})'.format(addPuntos(cant_venta), city, user)
			sendToBot(msg)
			s.post(payloadPost=data)

			if porVender == 0:
				sendToBot('porVender == 0')
				return
			if quiereComprar == 0:
				sendToBot('quiereComprar == 0')
				break
