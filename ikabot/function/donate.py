#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import gettext
from ikabot.config import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import *
from ikabot.helpers.recursos import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import addDot

t = gettext.translation('donate', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def donate(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		bienes = {'1': _('Vineyard'), '2': _('Quarry'), '3': _('Crystal Mine'), '4': _('Sulfur Pit')}
		banner()

		ciudad = chooseCity(s)
		banner()

		madera = ciudad['recursos'][0]
		almacenamiento = ciudad['storageCapacity']

		idIsla = ciudad['islandId']
		html = s.get(urlIsla + idIsla)
		isla = getIsla(html)

		tipo = isla['tipo']
		bien = bienes[tipo]

		urlAserradero = 'view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1'.format(idIsla, s.token())
		aserraderoOk = printEstadoMina(s, urlAserradero, 'Aserradero')

		urlBien = 'view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest={2}&ajax=1'.format(tipo, idIsla, s.token())
		bienOk = printEstadoMina(s, urlBien, bien)

		tipo = ['resource', 'tradegood']
		print(_('Wood available:{} / {}\n').format(addDot(madera), addDot(almacenamiento)))

		if aserraderoOk is True and bienOk is True:
			msg = _('Forest(1) o {}(2)?:').format(bien)
			tipoDonacion = read(msg=msg, min=1, max=2)
		elif aserraderoOk is True and bienOk is False:
			tipoDonacion = 1
			print(_('Forest:\n'))
		elif aserraderoOk is False and bienOk is True:
			tipoDonacion = 2
			print('{}:\n'.format(bien))
		else:
			print(_('You cannot donate\n'))
			return

		tipo = tipo[tipoDonacion - 1]

		cantidad = read(min=0, max=madera, msg=_('Amount:'))
		s.post(payloadPost={'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': cantidad, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})
		e.set()
	except KeyboardInterrupt:
		e.set()
		return

def printEstadoMina(s, url, bien):
	html = s.post(url)
	levels = re.search(r'"resourceLevel":"(\d+)","tradegoodLevel":"(\d+)"', html)
	if bien == _('Forest'):
		lv = levels.group(1)
	else:
		lv = levels.group(2)
	infoMina = re.search(r':<\\/h4>\\n\s*<ul\sclass=\\"resources\\">\\n\s*<li\sclass=\\"wood\\">([\d,]+)<[\s\S]*?:<\\/h4>\\n\s*<ul\sclass=\\"resources\\">\\n\s*<li\sclass=\\"wood\\">([\d,]+)<', html)
	if infoMina is not None:
		donado = infoMina.group(2)
		pordonate = infoMina.group(1)
		donado = int(donado.replace(',', ''))
		pordonate = int(pordonate.replace(',', ''))
		print('{} lv:{}'.format(bien, lv))
		print('{} / {} {}%'.format(addDot(donado), addDot(pordonate), addDot(int((100 * donado) / pordonate))))
	else:
		print(_('{}: Is expanding to level {:d}\n').format(bien, int(lv) + 1))
	return infoMina is not None
