#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re

urlCiudad = 'view=city&cityId='
urlIsla = 'view=island&islandId='

def donar(s):
	bienes = {'1': 'Viñedo', '2': 'Cantera', '3': 'Mina de cristal', '4': 'Mina de azufre'}
	banner()

	idCiudad = getIdCiudad(s)
	html = s.get(urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	banner()

	madera = getRescursosDisponibles(html)[0]
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
