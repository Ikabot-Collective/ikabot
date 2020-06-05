#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import math
import json
import gettext
import sys
from ikabot.helpers.pedirInfo import read
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.varios import *

t = gettext.translation('shipMovements',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def esHostil(movement):
	if movement['army']['amount']:
		return True
	for mov in movement['fleet']['ships']:
		if mov['cssClass'] != 'ship_transport':
			return True
	return False

def shipMovements(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		print(_('Ships {:d}/{:d}\n').format(getAvailableShips(s), getTotalShips(s)))

		html = s.get()
		idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
		posted = s.post(url)
		postdata = json.loads(posted, strict=False)
		movements = postdata[1][1][2]['viewScriptParams']['militaryAndFleetMovements']
		tiempoAhora = int(postdata[0][1]['time'])

		for movement in movements:

			color = ''
			if movement['isHostile']:
				color = bcolors.RED + bcolors.BOLD
			elif movement['isOwnArmyOrFleet']:
				color = bcolors.BLUE + bcolors.BOLD
			elif movement['isSameAlliance']:
				color = bcolors.GREEN + bcolors.BOLD

			origen  = '{} ({})'.format(movement['origin']['name'], movement['origin']['avatarName'])
			destino = '{} ({})'.format(movement['target']['name'], movement['target']['avatarName'])
			flecha = '<-' if movement['event']['isFleetReturning'] else '->'
			tiempoFaltante = int(movement['eventTime']) - tiempoAhora
			print('{}{} {} {}: {} ({}) {}'.format(color, origen, flecha, destino, movement['event']['missionText'], daysHoursMinutes(tiempoFaltante), bcolors.ENDC))

			if movement['isHostile']:
				tropas = movement['army']['amount']
				flotas = movement['fleet']['amount']
				print(_('Troops:{}\nFleets:{}').format(addDot(tropas), addDot(flotas)))
			elif esHostil(movement):
				tropas = movement['army']['amount']
				barcos = 0
				flotas = 0
				for mov in movement['fleet']['ships']:
					if mov['cssClass'] == 'ship_transport':
						barcos += int(mov['amount'])
					else:
						flotas += int(mov['amount'])
				print(_('Troops:{}\nFleets:{}\n Ships:{}').format(addDot(tropas), addDot(flotas), addDot(barcos)))
			else:
				bien = {'wood': _('wood'), 'wine': _('wine'), 'marble': _('marble'), 'glass': _('cristal'), 'sulfur': _('sulfur')}
				cargaTotal = 0
				for resource in movement['resources']:
					cantidad = resource['amount']
					tipo = resource['cssClass'].split()[1]
					tipo = bien[tipo]
					cargaTotal += int( cantidad.replace(',', '') )
					print(_('{} of {}').format(cantidad, tipo))
				barcos = int(math.ceil((Decimal(cargaTotal) / Decimal(500))))
				print(_('{:d} Ships').format(barcos))
		enter()
		e.set()
	except KeyboardInterrupt:
		e.set()
		return
