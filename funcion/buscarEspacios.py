#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import traceback
from helpers.signals import *
from helpers.botComm import *
from helpers.pedirInfo import *
from helpers.getJson import *
from helpers.process import *
from helpers.gui import *

def buscarEspacios(s):
	if botValido(s) is False:
		return
	print('Se buscarán espacios nuevos cada hora.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nBusco espacios nuevos en las islas cada 1 hora\n'
	setInfoSignal(s, info)
	idIslas = getIdsdeIslas(s)
	ciudades_espacios_dict = {}
	try:
		while True:
			for idIsla in idIslas:
				html = s.get(urlIsla + idIsla)
				isla = getIsla(html)
				espacios = 0
				ciudades = []
				for city in isla['cities']:
					if city['type'] == 'empty':
						espacios += 1
					else:
						ciudades.append(city)
				if idIsla in ciudades_espacios_dict:
					lugaresAntes = ciudades_espacios_dict[idIsla][1]
					ciudadesAntes = ciudades_espacios_dict[idIsla][0]
					ciudadesAhora = isla['cities']
					if lugaresAntes < espacios:
						# alguien desaparecio
						for cityAntes in ciudadesAntes:
							encontro = False
							for cityAhora in ciudadesAhora:
								if cityAhora['type'] != 'empty' and cityAhora['id'] == cityAntes['id']:
									encontro = True
									break
							if encontro is False:
								desaparecio = cityAntes
								break
						msg = '{} desapareció en {} {}:{} {}'.format(desaparecio['Name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
						sendToBot(s, msg)
					if lugaresAntes > espacios:
						# alguien fundo
						for cityAhora in ciudadesAhora:
							encontro = False
							for cityAntes in ciudadesAntes:
								if cityAhora['type'] != 'empty' and cityAhora['id'] == cityAntes['id']:
									encontro = True
									break
							if encontro is False:
								fundo = cityAhora
								break
						msg = '{} fundó en {} {}:{} {}'.format(fundo['Name'], tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
						sendToBot(s, msg)
				ciudades_espacios_dict[idIsla] = (ciudades, espacios)
			time.sleep(1*60*60)
	except:
		msg = 'Ya no se buscarán más espacios.\n{}'.format(traceback.format_exc())
		sendToBot(s, msg)
		s.logout()
