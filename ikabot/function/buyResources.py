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
from ikabot.helpers.planRoutes import waitForArrival
from ikabot.helpers.pedirInfo import getIdsOfCities, read
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.resources import *
from ikabot.helpers.market import *

t = gettext.translation('buyResources',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def chooseResource(session, city):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	city : dict
	"""
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
	'actionRequest': actionRequest,
	'ajax': 1
	}
	# this will set the chosen resource in the store
	session.post(payloadPost=data)
	resource = choise - 1
	# return the chosen resource
	return resource

def getOffers(session, city):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	city : dict
	Returns
	-------
	offers : list[dict]
	"""
	html = getMarketHtml(session, city)
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

def calculateCost(offers, total_amount_to_buy):
	"""
	Parameters
	----------
	offers : list[dict]
	total_amount_to_buy : int
	Returns
	-------
	total_cost : int
	"""
	total_cost = 0
	for offer in offers:
		if total_amount_to_buy == 0:
			break
		buy_amount = min(offer['amountAvailable'], total_amount_to_buy)
		total_amount_to_buy -= buy_amount
		total_cost += buy_amount * offer['precio']
	return total_cost

def getGold(session, city):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	city : dict
	Returns
	-------
	gold : int
	"""
	url = 'view=finances&backgroundView=city&currentCityId={}&templateView=finances&actionRequest={}&ajax=1'.format(city['id'], actionRequest)
	data = session.post(url)
	json_data = json.loads(data, strict=False)
	gold = json_data[0][1]['headerData']['gold']
	gold = gold.split('.')[0]
	gold = int(gold)
	return gold

def chooseCommertialCity(commercial_cities):
	"""
	Parameters
	----------
	commercial_cities : list[dict]

	Returns
	-------
	commercial_city : dict
	"""
	print(_('From which city do you want to buy resources?\n'))
	for i, city in enumerate(commercial_cities):
		print('({:d}) {}'.format(i + 1, city['name']))
	selected_city_index = read(min=1, max=len(commercial_cities))
	return commercial_cities[selected_city_index - 1]

def buyResources(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	try:
		banner()

		# get all the cities with a store
		commercial_cities = getCommercialCities(session)
		if len(commercial_cities) == 0:
			print(_('There is no store build'))
			enter()
			event.set()
			return

		# choose which city to buy from
		if len(commercial_cities) == 1:
			city = commercial_cities[0]
		else:
			city = chooseCommertialCity(commercial_cities)
			banner()

		# choose resource to buy
		resource = chooseResource(session, city)
		banner()

		# get all the offers of the chosen resource from the chosen city
		offers = getOffers(session, city)
		if len(offers) == 0:
			print(_('There are no offers available.'))
			event.set()
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
			event.set()
			return

		# calculate the total cost
		gold = getGold(session, city)
		total_cost = calculateCost(offers, amount_to_buy)

		print(_('\nCurrent gold: {}.\nTotal cost  : {}.\nFinal gold  : {}.'). format(addDot(gold), addDot(total_cost), addDot(gold - total_cost)))
		print(_('Proceed? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			event.set()
			return

		print(_('It will be purchased {}').format(addDot(amount_to_buy)))
		enter()
	except KeyboardInterrupt:
		event.set()
		return

	set_child_mode(session)
	event.set()

	info = _('\nI will buy {} from {} to {}\n').format(addDot(amount_to_buy), materials_names[resource], city['cityName'])
	setInfoSignal(session, info)
	try:
		do_it(session, city, offers, amount_to_buy)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(session, msg)
	finally:
		session.logout()

def buy(session, city, offer, amount_to_buy):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	city : dict
	offer : dict
	amount_to_buy : int
	"""
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
	'actionRequest': actionRequest,
	'ajax': 1
	}
	url = 'view=takeOffer&destinationCityId={}&oldView=branchOffice&activeTab=bargain&cityId={}&position={}&type={}&resource={}&backgroundView=city&currentCityId={}&templateView=branchOffice&actionRequest={}&ajax=1'.format(offer['destinationCityId'], offer['cityId'], offer['position'], offer['type'], offer['resource'], offer['cityId'], actionRequest)
	data = session.post(url)
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
	session.post(payloadPost=data_dict)
	msg = _('I buy {} to {} from {}').format(addDot(amount_to_buy), offer['ciudadDestino'], offer['jugadorAComprar'])
	sendToBotDebug(session, msg, debugON_buyResources)

def do_it(session, city, offers, amount_to_buy):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	city : dict
	offers : list[dict]
	amount_to_buy : int
	"""
	while True:
		for offer in offers:
			if amount_to_buy == 0:
				return
			if offer['amountAvailable'] == 0:
				continue

			ships_available = waitForArrival(session)
			storageCapacity  = ships_available * 500
			buy_amount = min(amount_to_buy, storageCapacity, offer['amountAvailable'])

			amount_to_buy -= buy_amount
			offer['amountAvailable'] -= buy_amount
			buy(session, city, offer, buy_amount)
			# start from the beginning again, so that we always buy from the cheapest offers fisrt
			break
