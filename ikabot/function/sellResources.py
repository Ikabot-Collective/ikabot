#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import math
import json
import gettext
import traceback
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.tienda import *
from ikabot.helpers.botComm import *
from ikabot.helpers.varios import addDot, wait
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.planearViajes import waitForArrival

t = gettext.translation('sellResources', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def chooseComertialCity(ciudades_comerciales):
	print(_('In which city do you want to sell resources?\n'))
	for i, ciudad in enumerate(ciudades_comerciales):
		print('({:d}) {}'.format(i + 1, ciudad['name']))
	ind = read(min=1, max=len(ciudades_comerciales))
	return ciudades_comerciales[ind - 1]

def getStoreInfo(s, ciudad):
	params = {'view': 'branchOfficeOwnOffers', 'activeTab': 'tab_branchOfficeOwnOffers', 'cityId': ciudad['id'], 'position': ciudad['pos'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'branchOfficeOwnOffers', 'currentTab': 'tab_branchOfficeOwnOffers', 'actionRequest': 'REQUESTID', 'ajax': '1'}
	resp = s.post(params=params, noIndex=True)
	return json.loads(resp, strict=False)[1][1][1]

def getOffers(s, ciudad, recurso):
	if recurso == 0:
		recurso = 'resource'
	else:
		recurso = str(recurso)
	data = {'cityId': ciudad['id'], 'position': ciudad['pos'], 'view': 'branchOffice', 'activeTab': 'bargain', 'type': '333', 'searchResource': recurso, 'range': ciudad['rango'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'branchOffice', 'currentTab': 'bargain', 'actionRequest': 'REQUESTID', 'ajax': '1'}
	resp = s.post(payloadPost=data)
	html = json.loads(resp, strict=False)[1][1][1]
	return re.findall(r'<td class=".*?">(.*?)<br/>\((.*?)\)\s*</td>\s*<td>(.*?)</td>\s*<td><img src=".*?"\s*alt=".*?"\s*title=".*?"/></td>\s*<td style="white-space:nowrap;">(\d+)\s*<img src=".*?"\s*class=".*?"/>.*?</td>\s*<td>(\d+)</td>\s*<td><a onclick="ajaxHandlerCall\(this\.href\);return false;"\s*href="\?view=takeOffer&destinationCityId=(\d+)&', html)

def sellToOffers(s, city_to_buy_from, resource, e):
	banner()

	offers = getOffers(s, city_to_buy_from, resource)

	if len(offers) == 0:
		print(_('No offers available.'))
		enter()
		e.set()
		return

	print(_('Which offers do you want to sell to?\n'))

	chosen_offers = []
	total_amount = 0
	profit = 0
	for offer in offers:
		cityname, username, amount, price, dist, destinyId = offer
		cityname = cityname.strip()
		amount = amount.replace(',', '').replace('.', '')
		amount = int(amount)
		price = int(price)
		msg = _('{} ({}): {} at {:d} each ({} in total) [Y/n]').format(cityname, username, addDot(amount), price, addDot(price*amount))
		rta = read(msg=msg, values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			continue
		chosen_offers.append(offer)
		total_amount += amount
		profit += amount * price

	if len(chosen_offers) == 0:
		e.set()
		return

	available = city_to_buy_from['recursos'][resource]
	amount_to_sell = min(available, total_amount)

	banner()
	print(_('\nHow much do you want to sell? [max = {}]').format(addDot(amount_to_sell)))
	amount_to_sell = read(min=0, max=amount_to_sell)
	if amount_to_sell == 0:
		e.set()
		return

	left_to_sell = amount_to_sell
	profit = 0
	for offer in chosen_offers:
		cityname, username, amount, price, dist, destinyId = offer
		cityname = cityname.strip()
		amount = amount.replace(',', '').replace('.', '')
		amount = int(amount)
		price = int(price)
		sell = min(amount, left_to_sell)
		left_to_sell -= sell
		profit += sell * price
	print(_('\nSell {} of {} for a total of {}? [Y/n]').format(addDot(amount_to_sell), materials_names[resource], addDot(profit)))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI sell {} of {} in {}\n').format(addDot(amount_to_sell), materials_names[resource], city_to_buy_from['name'])
	setInfoSignal(s, info)
	try:
		do_it1(s, amount_to_sell,  chosen_offers, resource, city_to_buy_from)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def createOffer(s, city, resource, e):
	banner()

	html = getStoreInfo(s, city)
	sell_store_capacity = storageCapacityOfStore(html)
	recurso_disp = city['recursos'][resource]

	print(_('How much do you want to sell? [max = {}]').format(addDot(recurso_disp)))
	amount_to_sell = read(min=0, max=recurso_disp)
	if amount_to_sell == 0:
		e.set()
		return

	price_max, price_min = re.findall(r'\'upper\': (\d+),\s*\'lower\': (\d+)', html)[resource]
	price_max = int(price_max)
	price_min = int(price_min)
	print(_('\nAt what price? [min = {:d}, max = {:d}]').format(price_min, price_max))
	price = read(min=price_min, max=price_max)

	print(_('\nI will sell {} of {} at {}: {}').format(addDot(amount_to_sell), materials_names[resource], addDot(price), addDot(price * amount_to_sell)))
	print(_('\nProceed? [Y/n]'))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI sell {} of {} in {}\n').format(addDot(amount_to_sell), materials_names[resource], city['name'])
	setInfoSignal(s, info)
	try:
		do_it2(s, amount_to_sell, price, resource, sell_store_capacity, city)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def sellResources(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		commertial_cities = getCommertialCities(s)
		if len(commertial_cities) == 0:
			print(_('There is no store built'))
			enter()
			e.set()
			return

		if len(commertial_cities) == 1:
			city = commertial_cities[0]
		else:
			city = chooseComertialCity(commertial_cities)
			banner()

		print(_('What resource do you want to sell?'))
		for index, material_name in enumerate(materials_names):
			print('({:d}) {}'.format(index+1, material_name))
		choise = read(min=1, max=len(materials_names))
		resource = choise - 1
		banner()

		print(_('Do you want to sell to existing offers (1) or do you want to make your own offer (2)?'))
		choise = read(min=1, max=2)
		[sellToOffers, createOffer][choise - 1](s, city, resource, e)
	except KeyboardInterrupt:
		e.set()
		return

def do_it1(s, left_to_sell, offers, resource, city_to_buy_from):
	for offer in offers:
		cityname, username, amount, precio, dist, idDestino = offer
		cityname = cityname.strip()
		amount_to_buy = amount.replace(',', '').replace('.', '')
		amount_to_buy = int(amount_to_buy)
		while True:
			amount_to_sell = min(amount_to_buy, left_to_sell)
			ships_available = waitForArrival(s)
			ships_needed = math.ceil((Decimal(amount_to_sell) / Decimal(500)))
			ships_used = min(ships_available, ships_needed)
			if ships_needed > ships_used:
				amount_to_sell = ships_used * 500
			left_to_sell -= amount_to_sell
			amount_to_buy -= amount_to_sell

			data = {'action': 'transportOperations', 'function': 'sellGoodsAtAnotherBranchOffice', 'cityId': city_to_buy_from['id'], 'destinationCityId': idDestino, 'oldView': 'branchOffice', 'position': city_to_buy_from['pos'], 'avatar2Name': username, 'city2Name': cityname, 'type': '333', 'activeTab': 'bargain', 'transportDisplayPrice': '0', 'premiumTransporter': '0', 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': str(ships_used), 'backgroundView': 'city', 'currentCityId': city_to_buy_from['id'], 'templateView': 'takeOffer', 'currentTab': 'bargain', 'actionRequest': 'REQUESTID', 'ajax': '1'}
			if resource == 0:
				data['cargo_resource'] = amount_to_sell
				data['resourcePrice'] = precio
			else:
				data['tradegood{:d}Price'.format(resource)] = precio
				data['cargo_tradegood{:d}'.format(resource)] = amount_to_sell

			s.get(urlCiudad + city_to_buy_from['id'], noIndex=True)
			s.post(payloadPost=data)

			if left_to_sell == 0:
				return
			if amount_to_buy == 0:
				break

def do_it2(s, amount_to_sell, price, resource, sell_store_capacity, city):
	initial_amount_to_sell = amount_to_sell
	html = getStoreInfo(s, city)
	previous_on_sell = onSellInStore(html)[resource]
	while True:
		html = getStoreInfo(s, city)
		currently_on_sell = onSellInStore(html)[resource]
		# if there is space in the store
		if currently_on_sell < storageCapacityOfStore(html):
			# add our new offer to the free space
			free_space = sell_store_capacity - currently_on_sell
			offer = min(amount_to_sell, free_space)
			amount_to_sell -= offer
			new_offer = currently_on_sell + offer

			payloadPost = {'cityId': city['id'], 'position': city['pos'], 'action': 'CityScreen', 'function': 'updateOffers', 'resourceTradeType': '444', 'resource': '0', 'resourcePrice': '10', 'tradegood1TradeType': '444', 'tradegood1': '0', 'tradegood1Price': '11', 'tradegood2TradeType': '444', 'tradegood2': '0', 'tradegood2Price': '12', 'tradegood3TradeType': '444', 'tradegood3': '0', 'tradegood3Price': '17', 'tradegood4TradeType': '444', 'tradegood4': '0', 'tradegood4Price': '5', 'backgroundView': 'city', 'currentCityId': city['id'], 'templateView': 'branchOfficeOwnOffers', 'currentTab': 'tab_branchOfficeOwnOffers', 'actionRequest': 'REQUESTID', 'ajax': '1'}
			if resource == 0:
				payloadPost['resource'] = new_offer
				payloadPost['resourcePrice'] = price
			else:
				payloadPost['tradegood{:d}'.format(resource)] = new_offer
				payloadPost['tradegood{:d}Price'.format(resource)] = price
			s.post(payloadPost=payloadPost)

			# if we don't have any more to add to the offer, leave the loop
			if amount_to_sell == 0:
				break

		# sleep for 2 hours
		wait(60 * 60 *  2)

	# wait until the last of our offer is actualy bought, and let the user know
	while True:
		html = getStoreInfo(s, city)
		currently_on_sell = onSellInStore(html)[resource]
		if currently_on_sell <= previous_on_sell:
			msg = _('{} of {} was sold at {:d}').format(addDot(initial_amount_to_sell), materials_names[resource], price)
			sendToBot(s, msg)
			return

		# sleep for 2 hours
		wait(60 * 60 *  2)
