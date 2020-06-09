#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import gettext
import json
from ikabot.config import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import *
from ikabot.helpers.recursos import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *

t = gettext.translation('donate', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def donate(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()

		city = chooseCity(s)
		banner()

		woodAvailable = city['recursos'][0]

		islandId = city['islandId']
		html = s.get(urlIsla + islandId)
		island = getIsland(html)

		island_type = island['tipo']
		resource_name  = tradegoods_names[0]
		tradegood_name = tradegoods_names[int(island_type)]

		# get resource information
		url = 'view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest=REQUESTID&ajax=1'.format(islandId)
		resp = s.post(url)
		resp = json.loads(resp, strict=False)

		resourceLevel  = resp[0][1]['backgroundData']['resourceLevel']
		tradegoodLevel = resp[0][1]['backgroundData']['tradegoodLevel']
		resourceEndUpgradeTime = resp[0][1]['backgroundData']['resourceEndUpgradeTime']
		resourceUpgrading = resourceEndUpgradeTime > 0
		tradegoodEndUpgradeTime = resp[0][1]['backgroundData']['tradegoodEndUpgradeTime']
		tradegoodUpgrading = tradegoodEndUpgradeTime > 0

		if resourceUpgrading:
			resourceUpgradeMsg = _('(upgrading, ends in:{})').format(daysHoursMinutes(resourceEndUpgradeTime))
		else:
			resourceUpgradeMsg = ''
		if tradegoodUpgrading:
			tradegoodUpgradeMsg = _('(upgrading, ends in:{})').format(daysHoursMinutes(tradegoodEndUpgradeTime))
		else:
			tradegoodUpgradeMsg = ''

		html = resp[1][1][1]
		wood_total_needed, wood_donated = re.findall(r'<li class="wood">(.*?)</li>', html)
		wood_total_needed = wood_total_needed.replace(',', '').replace('.', '')
		wood_total_needed = int(wood_total_needed)
		wood_donated = wood_donated.replace(',', '').replace('.', '')
		wood_donated = int(wood_donated)

		if resourceUpgrading and tradegoodUpgrading:
			print(_('Both the {} (ends in:{}) and the {} (ends in:{}) are being upgraded rigth now.\n'.format(resource_name, daysHoursMinutes(resourceEndUpgradeTime), tradegood_name, daysHoursMinutes(tradegoodEndUpgradeTime))))
			enter()
			e.set()
			return

		print('{} lv:{} {}'.format(resource_name, resourceLevel, resourceUpgradeMsg))
		print('{} / {} ({}%)\n'.format(addDot(wood_donated), addDot(wood_total_needed), addDot(int((100 * wood_donated) / wood_total_needed))))

		# get tradegood information
		url = 'view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest=REQUESTID&ajax=1'.format(island_type, islandId)
		resp = s.post(url)

		resp = json.loads(resp, strict=False)
		html = resp[1][1][1]
		tradegood_total_needed, tradegood_donated = re.findall(r'<li class="wood">(.*?)</li>', html)
		tradegood_total_needed = tradegood_total_needed.replace(',', '').replace('.', '')
		tradegood_total_needed = int(tradegood_total_needed)
		tradegood_donated = tradegood_donated.replace(',', '').replace('.', '')
		tradegood_donated = int(tradegood_donated)

		print('{} lv:{} {}'.format(tradegood_name, tradegoodLevel, tradegoodUpgradeMsg))
		print('{} / {} ({}%)\n'.format(addDot(tradegood_donated), addDot(tradegood_total_needed), addDot(int((100 * tradegood_donated) / tradegood_total_needed))))

		print(_('Wood available:{}\n').format(addDot(woodAvailable)))

		if resourceUpgrading is False and tradegoodUpgrading is False:
			msg = _('Donate to {} (1) or {} (2)?:').format(resource_name, tradegood_name)
			donation_type = read(msg=msg, min=1, max=2)
			name = resource_name if donation_type == 1 else tradegood_name
			print('')
		else:
			if resourceUpgrading is False and tradegoodUpgrading is True:
				donation_type = 1
				name = resource_name
			else:
				donation_type = 2
				name = tradegood_name
			print('Donate to:{}\n'.format(name))

		donation_type = 'resource' if donation_type == 1 else 'tradegood'

		amount = read(min=0, max=woodAvailable, msg=_('Amount:'))
		if amount == 0:
			e.set()
			return
		print(_('Will donate {} to the {}?').format(addDot(amount), name))
		print(_('\nProceed? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			return

		# do the donation
		s.post(payloadPost={'islandId': islandId, 'type': donation_type, 'action': 'IslandScreen', 'function': 'donate', 'donation': amount, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': 'REQUESTID', 'ajax': '1'})

		print('\nDonation successful.')
		enter()
		e.set()
		return
	except KeyboardInterrupt:
		e.set()
		return
