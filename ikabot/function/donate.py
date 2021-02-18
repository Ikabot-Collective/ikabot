#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import gettext
import json
from ikabot.config import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import *
from ikabot.helpers.resources import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *

t = gettext.translation('donate',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def donate(session, event, stdin_fd, predetermined_input):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	predetermined_input : multiprocessing.managers.SyncManager.list
	"""
	sys.stdin = os.fdopen(stdin_fd)
	config.predetermined_input = predetermined_input
	try:
		banner()

		city = chooseCity(session)
		banner()

		woodAvailable = city['recursos'][0]

		islandId = city['islandId']
		html = session.get(island_url + islandId)
		island = getIsland(html)

		island_type = island['tipo']
		resource_name  = tradegoods_names[0]
		tradegood_name = tradegoods_names[int(island_type)]

		# get resource information
		url = 'view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1'.format(islandId, actionRequest)
		resp = session.post(url)
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
			event.set()
			return

		print('{} lv:{} {}'.format(resource_name, resourceLevel, resourceUpgradeMsg))
		print('{} / {} ({}%)\n'.format(addThousandSeparator(wood_donated), addThousandSeparator(wood_total_needed), addThousandSeparator(int((100 * wood_donated) / wood_total_needed))))

		# get tradegood information
		url = 'view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest={2}&ajax=1'.format(island_type, islandId, actionRequest)
		resp = session.post(url)

		resp = json.loads(resp, strict=False)
		html = resp[1][1][1]
		tradegood_total_needed, tradegood_donated = re.findall(r'<li class="wood">(.*?)</li>', html)
		tradegood_total_needed = tradegood_total_needed.replace(',', '').replace('.', '')
		tradegood_total_needed = int(tradegood_total_needed)
		tradegood_donated = tradegood_donated.replace(',', '').replace('.', '')
		tradegood_donated = int(tradegood_donated)

		print('{} lv:{} {}'.format(tradegood_name, tradegoodLevel, tradegoodUpgradeMsg))
		print('{} / {} ({}%)\n'.format(addThousandSeparator(tradegood_donated), addThousandSeparator(tradegood_total_needed), addThousandSeparator(int((100 * tradegood_donated) / tradegood_total_needed))))

		print(_('Wood available:{}\n').format(addThousandSeparator(woodAvailable)))

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
			event.set()
			return
		print(_('Will donate {} to the {}?').format(addThousandSeparator(amount), name))
		print(_('\nProceed? [Y/n]'))
		rta = read(values=['y', 'Y', 'n', 'N', ''])
		if rta.lower() == 'n':
			return

		# do the donation
		session.post(payloadPost={'islandId': islandId, 'type': donation_type, 'action': 'IslandScreen', 'function': 'donate', 'donation': amount, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': actionRequest, 'ajax': '1'})

		print('\nDonation successful.')
		enter()
		event.set()
		return
	except KeyboardInterrupt:
		event.set()
		return
