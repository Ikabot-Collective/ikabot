#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from ikabot.config import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import *
from ikabot.helpers.recursos import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import addPuntos

def donar(s):
	bienes = {'1': 'Viñedo', '2': 'Cantera', '3': 'Mina de cristal', '4': 'Mina de azufre'}
	banner()

	ciudad = elegirCiudad(s)
	html = ciudad['html']
	banner()

	madera = getRecursosDisponibles(html)[0]
	almacenamiento = getCapacidadDeAlmacenamiento(html)

	idIsla = ciudad['islandId']
	html = s.get(urlIsla + idIsla)
	isla = getIsla(html)

	tipo = re.search(r'"tradegood":"(\d)"', html).group(1)
	bien = bienes[tipo]

	urlAserradero = 'view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1'.format(idIsla, s.token())
	aserraderoOk = printEstadoMina(s, urlAserradero, 'Aserradero')

	urlBien = 'view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest={2}&ajax=1'.format(tipo, idIsla, s.token())
	bienOk = printEstadoMina(s, urlBien, bien)

	tipo = ['resource', 'tradegood']
	print('Madera disopnible:{} / {}\n'.format(addPuntos(madera), addPuntos(almacenamiento)))

	if aserraderoOk is True and bienOk is True:
		msg = 'Aserradero(1) o ' + bien + '(2)?:'
		tipoDonacion = read(msg=msg, min=1, max=2)
	elif aserraderoOk is True and bienOk is False:
		tipoDonacion = 1
		print('Aserradero:\n')
	elif aserraderoOk is False and bienOk is True:
		tipoDonacion = 2
		print('{}:\n'.format(bien))
	else:
		print('No se puede donar\n')
		return

	tipo = tipo[tipoDonacion - 1]

	cantidad = read(min=0, max=int(madera), msg='Cantidad:')
	s.post(payloadPost={'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': cantidad, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})

def printEstadoMina(s, url, bien):
	html = s.post(url)
	levels = re.search(r'"resourceLevel":"(\d+)","tradegoodLevel":"(\d+)"', html)
	if bien == 'Aserradero':
		lv = levels.group(1)
	else:
		lv = levels.group(2)
	infoMina = re.search(r':<\\/h4>\\n\s*<ul\sclass=\\"resources\\">\\n\s*<li\sclass=\\"wood\\">([\d,]+)<[\s\S]*?:<\\/h4>\\n\s*<ul\sclass=\\"resources\\">\\n\s*<li\sclass=\\"wood\\">([\d,]+)<', html)
	if infoMina is not None:
		donado = infoMina.group(2)
		porDonar = infoMina.group(1)
		donado = int(donado.replace(',', ''))
		porDonar = int(porDonar.replace(',', ''))
		print('{} lv:{}'.format(bien, lv))
		print('{} / {} {}%'.format(addPuntos(donado), addPuntos(porDonar), addPuntos(int((100 * donado) / porDonar))))
	else:
		print('{}: Está ampliando al nivel {:d}\n'.format(bien, int(lv) + 1))
	return infoMina is not None
