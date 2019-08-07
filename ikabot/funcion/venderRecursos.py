#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.tienda import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import forkear
from ikabot.helpers.varios import addPuntos
from ikabot.helpers.signals import setInfoSignal

t = gettext.translation('venderRecursos', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def getStoreInfo(s, ciudad):
	params = {'view': 'branchOfficeOwnOffers', 'activeTab': 'tab_branchOfficeOwnOffers', 'cityId': ciudad['id'], 'position': ciudad['pos'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'branchOfficeOwnOffers', 'currentTab': 'tab_branchOfficeOwnOffers', 'actionRequest': s.token(), 'ajax': '1'}
	resp = s.post(params=params, noIndex=True)
	return json.loads(resp, strict=False)[1][1][1]

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

	html = getStoreInfo(s, ciudad)
	cap_venta = getCapacidadDeVenta(html)
	recurso_disp = ciudad['recursos'][recurso]
	print(_('¿Cuánto quiere vender? [max = {}]').format(addPuntos(recurso_disp)))
	vender = read(min=0, max=recurso_disp)
	if vender == 0:
		return
	banner()

	precio_max, precio_min = re.findall(r'\'upper\': (\d+),\s*\'lower\': (\d+)', html)[recurso]
	precio_max = int(precio_max)
	precio_min = int(precio_min)
	print(_('\n¿A qué precio? [min = {:d}, max = {:d}]').format(precio_min, precio_max))
	precio = read(min=precio_min, max=precio_max)
	banner()

	print(_('\nSe venderá {} de {} a {}: {}').format(addPuntos(vender), tipoDeBien[recurso], addPuntos(precio), addPuntos(precio * vender)))
	print(_('\n¿Proceder? [Y/n]'))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		return

	forkear(s)
	if s.padre is True:
		return

	info = _('\nVendo {} de {} en {}\n').format(addPuntos(vender), tipoDeBien[recurso], ciudad['name'])
	setInfoSignal(s, info)
	try:
		do_it(s, vender, precio, recurso, cap_venta, ciudad)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def venderRecurso(s, sell, recurso, precio, ciudad):
	payloadPost = {'cityId': ciudad['id'], 'position': ciudad['pos'], 'action': 'CityScreen', 'function': 'updateOffers', 'resourceTradeType': '444', 'resource': '0', 'resourcePrice': '10', 'tradegood1TradeType': '444', 'tradegood1': '0', 'tradegood1Price': '11', 'tradegood2TradeType': '444', 'tradegood2': '0', 'tradegood2Price': '12', 'tradegood3TradeType': '444', 'tradegood3': '0', 'tradegood3Price': '17', 'tradegood4TradeType': '444', 'tradegood4': '0', 'tradegood4Price': '5', 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'branchOfficeOwnOffers', 'currentTab': 'tab_branchOfficeOwnOffers', 'actionRequest': s.token(), 'ajax': '1'}
	if recurso == 0:
		payloadPost['resource'] = str(sell)
		payloadPost['resourcePrice'] = str(precio)
	else:
		payloadPost['tradegood{:d}'.format(recurso)] = str(sell)
		payloadPost['tradegood{:d}Price'.format(recurso)] = str(precio)
	s.post(payloadPost=payloadPost)

def do_it(s, porVender, precio, recurso, cap_venta, ciudad):
	total = porVender
	html = getStoreInfo(s, ciudad)
	enVenta_inicial = vendiendo(html)[recurso]
	while True:
		html = getStoreInfo(s, ciudad)
		enVenta = vendiendo(html)[recurso]
		if enVenta < getCapacidadDeVenta(html):
			espacio = cap_venta - enVenta
			ofertar = porVender if espacio > porVender else espacio
			porVender -= ofertar
			nuevaVenta = enVenta + ofertar
			venderRecurso(s, nuevaVenta, recurso, precio, ciudad)
			if porVender == 0:
				break
		time.sleep(60 * 60 *  2)
	while True:
		html = getStoreInfo(s, ciudad)
		enVenta = vendiendo(html)[recurso]
		if enVenta <= enVenta_inicial:
			msg = _('Se vendieron {} de {} a {:d}').format(addPuntos(total), tipoDeBien[recurso], precio)
			sendToBot(msg)
			return
		time.sleep(60 * 60 *  2)
