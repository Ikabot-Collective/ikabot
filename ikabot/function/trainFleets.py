#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.varios import addDot
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.recursos import getRecursosDisponibles

t = gettext.translation('trainFleets',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def getShipyardInfo(s, city):
	params = {'view': 'shipyard', 'cityId': city['id'], 'position': city['pos'], 'backgroundView': 'city', 'currentCityId': city['id'], 'actionRequest': s.token(), 'ajax': '1'}
	data = s.post(params=params)
	return json.loads(data, strict=False)

def train(s, city, trainings):
	payload = {'action': 'CityScreen', 'function': 'buildShips', 'actionRequest': s.token(), 'cityId': city['id'], 'position': city['pos'], 'backgroundView': 'city', 'currentCityId': city['id'], 'templateView': 'shipyard', 'ajax': '1'}
	for training in trainings:
		payload[ training['unit_type_id'] ] = training['train']
	s.post(payloadPost=payload)

def waitForTraining(s, ciudad):
	data = getShipyardInfo(s, ciudad)
	html = data[1][1][1]
	seconds = re.search(r'\'buildProgress\', (\d+),', html)
	if seconds:
		seconds = seconds.group(1)
		seconds = int(seconds) - data[0][1]['time']
		wait(seconds + 5)

def planTrainings(s, city, trainings):
	shipyardPos = city['pos']

	# trainings might be divided in multriple rounds
	while True:

		# total number of units to create
		total = sum( [ fleet['cantidad'] for training in trainings for fleet in training ] )
		if total == 0:
			return

		for training in trainings:
			waitForTraining(s, city)
			html = s.get(urlCiudad + city['id'])
			city = getCiudad(html)
			city['pos'] = shipyardPos

			resourcesAvailable = city['recursos'].copy()
			resourcesAvailable.append( city['ciudadanosDisp'] )

			# for each fleet type in training
			for fleet in training:

				# calculate how many units can actually be trained based on the resources available
				fleet['train'] = fleet['cantidad']

				for i in range(len(materials_names_english)):
					material_name = materials_names_english[i].lower()
					if material_name in fleet['costs']:
						limiting = resourcesAvailable[i] // fleet['costs'][material_name]
						if limiting < fleet['train']:
							fleet['train'] = limiting

				if 'citizens' in fleet['costs']:
					limiting = resourcesAvailable[len(materials_names_english)] // fleet['costs']['citizens']
					if limiting < fleet['train']:
						fleet['train'] = limiting

				# calculate the resources that will be left
				for i in range(len(materials_names_english)):
					material_name = materials_names_english[i].lower()
					if material_name in fleet['costs']:
						resourcesAvailable[i] -= fleet['costs'][material_name] * fleet['train']

				if 'citizens' in fleet['costs']:
					resourcesAvailable[len(materials_names_english)] -= fleet['costs']['citizens'] * fleet['train']

				fleet['cantidad'] -= fleet['train']

			total = 0
			for fleet in training:
				total += fleet['train']
			if total == 0:
				msg = _('It was not possible to finish the training of fleets due to lack of resources.')
				sendToBot(s, msg)
				return

			train(s, city, training)

def generateFleet(unidades_info):
	i = 1
	unidades = []
	while 'js_barracksSlider{:d}'.format(i) in unidades_info:
		# {"identifier":"phalanx","unit_type_id":303,"costs":{"citizens":1,"wood":27,"sulfur":30,"upkeep":3,"completiontime":71.169695412658},"local_name":"Hoplita"}
		info = unidades_info['js_barracksSlider{:d}'.format(i)]['slider']['control_data']
		info = json.loads(info, strict=False)
		unidades.append(info)
		i += 1
	return unidades

def trainFleets(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()
		print(_('In what city do you want to train the fleet?'))
		city = chooseCity(s)
		banner()

		for i in range(len(city['position'])):
			if city['position'][i]['building'] == 'shipyard':
				city['pos'] = str(i)
				break
		else:
			print(_('Shipyard not built.'))
			enter()
			e.set()
			return

		data = getShipyardInfo(s, city)

		units_info = data[2][1]
		units = generateFleet(units_info)

		maxSize = max( [ len(unit['local_name']) for unit in units ] )

		tranings = []
		while True:
			units = generateFleet(units_info)
			print(_('Train:'))
			for unit in units:
				pad = ' ' * ( maxSize - len(unit['local_name']) )
				amount = read(msg='{}{}:'.format(pad, unit['local_name']), min=0, empty=True)
				if amount == '':
					amount = 0
				unit['cantidad'] = amount

			# calculate costs
			cost = [0] * ( len(materials_names_english) + 3 )
			for unit in units:

				for i in range(len(materials_names_english)):
					material_name = materials_names_english[i].lower()
					if material_name in unit['costs']:
						cost[i] += unit['costs'][material_name] * unit['cantidad']

				if 'citizens' in unit['costs']:
					cost[len(materials_names_english)+0] += unit['costs']['citizens'] * unit['cantidad']
				if 'upkeep' in unit['costs']:
					cost[len(materials_names_english)+1] += unit['costs']['upkeep'] * unit['cantidad']
				if 'completiontime' in unit['costs']:
					cost[len(materials_names_english)+2] += unit['costs']['completiontime'] * unit['cantidad']

			print(_('\nTotal cost:'))
			for i in range(len(materials_names_english)):
				if cost[i] > 0:
					print('{}: {}'.format(materials_names_english[i], addDot(cost[i])))
			if cost[len(materials_names_english)+0] > 0:
				print(_('Citizens: {}').format(addDot(cost[len(materials_names_english)+0])))
			if cost[len(materials_names_english)+1] > 0:
				print(_('Maintenance: {}').format(addDot(cost[len(materials_names_english)+1])))
			if cost[len(materials_names_english)+2] > 0:
				print(_('Duration: {}').format(daysHoursMinutes(int(cost[len(materials_names_english)+2]))))

			print(_('\nProceed? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				e.set()
				return

			tranings.append(units)

			print(_('\nDo you want to train more fleets when you finish? [y/N]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'y':
				banner()
				continue
			else:
				break

		# calculate if the city has enough resources
		resourcesAvailable = city['recursos'].copy()
		resourcesAvailable.append( city['ciudadanosDisp'] )

		for entrenamiento in tranings:
			for unit in entrenamiento:

				for i in range(len(materials_names_english)):
					material_name = materials_names_english[i].lower()
					if material_name in unit['costs']:
						resourcesAvailable[i] -= unit['costs'][material_name] * unit['cantidad']

				if 'citizens' in unit['costs']:
					resourcesAvailable[len(materials_names_english)] -= unit['costs']['citizens'] * unit['cantidad']

		not_enough = [ elem for elem in resourcesAvailable if elem < 0 ] != []

		if not_enough:
			print(_('\nThere are not enough resources:'))
			for i in range(len(materials_names_english)):
				if resourcesAvailable[i] < 0:
					print('{}:{}'.format(materials_names[i], addDot(resourcesAvailable[i]*-1)))

			if resourcesAvailable[len(materials_names_english)] < 0:
				print(_('Citizens:{}').format(addDot(resourcesAvailable[len(materials_names_english)]*-1)))

			print(_('\nProceed anyway? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				e.set()
				return

		print(_('\nThe selected fleet will be trained.'))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI train a fleet in {}\n').format(city['cityName'])
	setInfoSignal(s, info)
	try:
		planTrainings(s, city, tranings)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()
