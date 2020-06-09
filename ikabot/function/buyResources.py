#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import math
import json
import gettext
import traceback
from decimal import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.varios import addDot
from ikabot.helpers.gui import enter, banner
from ikabot.helpers.getJson import getCity
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.planearViajes import waitForArrival
from ikabot.helpers.pedirInfo import getIdsOfCities, read
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.recursos import *
from ikabot.helpers.tienda import *

t = gettext.translation('buyResources', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def chooseResource(s, city):
	print(_('Which resource do you want to buy?'))
	for index, material_name in enumerate(materials_names):
		print('({:d}) {}'.format(index+1, material_name))
	choise = read(min=1, max=5)
	resource = choise - 1
	if resource == 0:
		resource = 'resource'
	data = {
	'cityId': city['id'],
	'position': city['pos'],
	'view': 'branchOffice',
	'activeTab': 'bargain',
	'type': 444,
	'searchResource': resource,
	'range': city['rango'],
	'backgroundView' : 'city',
	'currentCityId': city['id'],
	'templateView': 'branchOffice',
	'currentTab': 'bargain',
	'actionRequest': 'REQUESTID',
	'ajax': 1
	}
	# this will set the chosen resource in the store
	s.post(payloadPost=data)
	resource = choise - 1
	# return the chosen resource
	return resource

def getOffers(s, city):
	html = getStoreHtml(s, city)
	hits = re.findall(r'short_text80">(.*?) *<br/>\((.*?)\)\s *</td>\s *<td>(\d+)</td>\s *<td>(.*?)/td>\s *<td><img src="skin/resources/icon_(\w+)\.png[\s\S]*?white-space:nowrap;">(\d+)\s[\s\S]*?href="\?view=takeOffer&destinationCityId=(\d+)&oldView=branchOffice&activeTab=bargain&cityId=(\d+)&position=(\d+)&type=(\d+)&resource=(\w+)"', html)
	offers = []
	for hit in hits:
		offer = {
		'ciudadDestino': hit[0],
		'jugadorAComprar' : hit[1],
		'bienesXminuto': int(hit[2]),
		'amountAvailable': int(hit[3].replace(',', '').replace('.', '').replace('<', '')),
		'tipo': hit[4],
		'precio': int(hit[5]),
		'destinationCityId': hit[6],
		'cityId': hit[7],
		'position': hit[8],
		'type': hit[9],
		'resource': hit[10]
		}
		offers.append(offer)
	return offers

def calculateCost(offers, amount_to_buy):
	total_cost = 0
	for offer in offers:
		if amount_to_buy == 0:
			break
		buy = min(offer['amountAvailable'], amount_to_buy)
		amount_to_buy -= buy
		total_cost += buy * offer['precio']
	return total_cost

def getGold(s, ciudad):
	url = 'view=finances&backgroundView=city&currentCityId={}&templateView=finances&actionRequest=REQUESTID&ajax=1'.format(ciudad['id'])
	data = s.post(url)
	json_data = json.loads(data, strict=False)
	gold = json_data[0][1]['headerData']['gold']
	gold = gold.split('.')[0]
	gold = int(gold)
	return gold

def chooseCommertialCity(commercial_cities):
	print(_('From which city do you want to buy resources?\n'))
	for i, ciudad in enumerate(commercial_cities):
		print('({:d}) {}'.format(i + 1, ciudad['name']))
	ind = read(min=1, max=len(commercial_cities))
	return commercial_cities[ind - 1]

def buyResources(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		# get all the cities with a store
		commercial_cities = getCommertialCities(s)
		if len(commercial_cities) == 0:
			print(_('There is no store build'))
			enter()
			e.set()
			return

		# choose which city to buy from
		if len(commercial_cities) == 1:
			city = commercial_cities[0]
		else:
			city = chooseCommertialCity(commercial_cities)
			banner()

		# choose resource to buy
		resource = chooseResource(s, city)
		banner()

		# get all the offers of the chosen resource from the chosen city
		offers = getOffers(s, city)
		if len(offers) == 0:
			print(_('There are no offers available.'))
			e.set()
			return

		# display offers to the user
		total_price   = 0
		total_amount = 0
		for offer in offers:
			amount = offer['amountAvailable']
			price  = offer['precio']
			cost   = amount * price
			print(_('amount:{}').format(addDot(amount)))
			print(_('price :{:d}').format(price))
			print(_('cost  :{}').format(addDot(cost)))
			print('')
			total_price += cost
			total_amount += amount

		# ask how much to buy
		print(_('Total amount available to purchase: {}, for {}').format(addDot(total_amount), addDot(total_price)))
		available = city['freeSpaceForResources'][resource]
		if available < total_amount:
			print(_('You just can buy {} due to storing capacity').format(addDot(available)))
			total_amount = available
		print('')
		amount_to_buy = read(msg=_('How much do you want to buy?: '), min=0, max=total_amount)
		if amount_to_buy == 0:
			e.set()
			return

		# calculate the total cost
		gold = getGold(s, city)
		total_cost = calculateCost(offers, amount_to_buy)

		print(_('\nCurrent gold: {}.\nTotal cost  : {}.\nFinal gold  : {}.'). format(addDot(gold), addDot(total_cost), addDot(gold - total_cost)))
		print(_('Proceed? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			e.set()
			return

		print(_('It will be purchased {}').format(addDot(amount_to_buy)))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI will buy {} from {} to {}\n').format(addDot(amount_to_buy), materials_names[resource], city['cityName'])
	setInfoSignal(s, info)
	try:
		do_it(s, city, offers, amount_to_buy)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()

def buy(s, city, offer, amount_to_buy):
	ships = int(math.ceil((Decimal(amount_to_buy) / Decimal(500))))
	data_dict = {
	'action': 'transportOperations',
	'function': 'buyGoodsAtAnotherBranchOffice',
	'cityId': offer['cityId'],
	'destinationCityId': offer['destinationCityId'],
	'oldView': 'branchOffice',
	'position': city['pos'],
	'avatar2Name': offer['jugadorAComprar'],
	'city2Name': offer['ciudadDestino'],
	'type': int(offer['type']),
	'activeTab': 'bargain',
	'transportDisplayPrice': 0,
	'premiumTransporter': 0,
	'capacity': 5,
	'max_capacity': 5,
	'jetPropulsion': 0,
	'transporters': ships,
	'backgroundView': 'city',
	'currentCityId': offer['cityId'],
	'templateView': 'takeOffer',
	'currentTab': 'bargain',
	'actionRequest': 'REQUESTID',
	'ajax': 1
	}
	url = 'view=takeOffer&destinationCityId={}&oldView=branchOffice&activeTab=bargain&cityId={}&position={}&type={}&resource={}&backgroundView=city&currentCityId={}&templateView=branchOffice&actionRequest=REQUESTID&ajax=1'.format(offer['destinationCityId'], offer['cityId'], offer['position'], offer['type'], offer['resource'], offer['cityId'])
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
	resource = offer['resource']
	if resource == 'resource':
		data_dict['cargo_resource'] = amount_to_buy
	else:
		data_dict['cargo_tradegood{}'.format(resource)] = amount_to_buy
	s.post(payloadPost=data_dict)
	msg = _('I buy {} to {} from {}').format(addDot(amount_to_buy), offer['ciudadDestino'], offer['jugadorAComprar'])
	sendToBotDebug(s, msg, debugON_buyResources)

def do_it(s, city, offers, amount_to_buy):
	while True:
		for offer in offers:
			if amount_to_buy == 0:
				return
			if offer['amountAvailable'] == 0:
				continue

			ships_available = waitForArrival(s)
			storageCapacity  = ships_available * 500
			buy_amount = min(amount_to_buy, storageCapacity, offer['amountAvailable'])

			amount_to_buy -= buy_amount
			offer['amountAvailable'] -= buy_amount
			buy(s, city, offer, buy_amount)
			# start from the beginning again, so that we always buy from the cheapest offers fisrt
			break
