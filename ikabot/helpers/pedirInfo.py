#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import json
import gettext
from decimal import *
from ikabot.config import *
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *

t = gettext.translation('pedirInfo', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

getcontext().prec = 30

def read(min=None, max=None, digit=False, msg=prompt, values=None): # lee input del usuario
	def _invalido():
		print('\033[1A\033[K', end="") # Borro linea
		return read(min, max, digit, msg, values)

	try:
		leido = input(msg)
	except EOFError:
		return _invalido()

	if digit is True or min is not None or max is not None:
		if leido.isdigit() is False:
			return _invalido()
		else:
			try:
				leido = eval(leido)
			except SyntaxError:
				return _invalido()
	if min is not None and leido < min:
		return _invalido()
	if max is not None and leido > max:
		return _invalido()
	if values is not None and leido not in values:
		return _invalido()
	return leido

def elegirCiudad(s, ajenas=False):
	(ids, ciudades) = getIdsDeCiudades(s)
	maxNombre = 0
	for unId in ids:
		largo = len(ciudades[unId]['name'])
		if largo > maxNombre:
			maxNombre = largo
	pad = lambda name: ' ' * (maxNombre - len(name) + 2)
	bienes = {'1': '(V)', '2': '(M)', '3': '(C)', '4': '(A)'}
	prints = []
	i = 0
	if ajenas:
		print(_(' 0: ciudad ajena'))
	else:
		print('')
	for unId in ids:
		i += 1
		tradegood = ciudades[unId]['tradegood']
		bien = bienes[tradegood]
		nombre = ciudades[unId]['name']
		num = ' ' + str(i) if i < 10 else str(i)
		print('{}: {}{}{}'.format(num, nombre, pad(nombre), bien))
	if ajenas:
		eleccion = read(min=0, max=i)
	else:
		eleccion = read(min=1, max=i)
	if eleccion == 0:
		return elegirCiudadAjena(s)
	else:
		html = s.get(urlCiudad + ids[eleccion -1])
		return getCiudad(html)

def elegirCiudadAjena(s):
	banner()
	x = read(msg='coordenada x:', digit=True)
	y = read(msg='coordenada y:', digit=True)
	print('')
	url = 'view=worldmap_iso&islandX={}&islandY={}&oldBackgroundView=island&islandWorldviewScale=1'.format(x, y)
	html = s.get(url)
	try:
		jsonIslas = re.search(r'jsonData = \'(.*?)\';', html).group(1)
		jsonIslas = json.loads(jsonIslas, strict=False)
		idIsla = jsonIslas['data'][str(x)][str(y)][0]
	except:
		print(_('Coordenadas incorrectas'))
		enter()
		banner()
		return elegirCiudad(s, ajenas=True)
	html = s.get(urlIsla + idIsla)
	isla = getIsla(html)
	maxNombre = 0
	for ciudad in isla['cities']:
		if ciudad['type'] == 'city':
			largo = len(ciudad['name'])
			if largo > maxNombre:
				maxNombre = largo
	pad = lambda name: ' ' * (maxNombre - len(name) + 2)
	i = 0
	opciones = []
	for ciudad in isla['cities']:
		if ciudad['type'] == 'city' and ciudad['state'] == '' and ciudad['Name'] != s.username:
			i += 1
			num = ' ' + str(i) if i < 10 else str(i)
			print('{}: {}{}({})'.format(num, ciudad['name'], pad(ciudad['name']), ciudad['Name']))
			opciones.append(ciudad)
	if i == 0:
		print(_('No hay ciudades donde enviar recursos en esta isla'))
		enter()
		return elegirCiudad(s, ajenas=True)
	eleccion = read(min=1, max=i)
	ciudad = opciones[eleccion - 1]
	ciudad['islandId'] = isla['id']
	ciudad['cityName'] = ciudad['name']
	ciudad['propia'] = False
	return ciudad

def getEdificios(s, idCiudad):
	html = s.get(urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	i = 0
	pos = -1
	prints = []
	posiciones = []
	prints.append(_('(0)\t\tsalir'))
	posiciones.append(None)
	for posicion in ciudad['position']:
		pos += 1
		if posicion['name'] != 'empty':
			i += 1
			level = posicion['level']
			if int(level) < 10:
				level = ' ' + level
			if posicion['isBusy']:
				level = level + '+'
			prints.append(_('({:d})\tlv:{}\t{}').format(i, level, posicion['name']))
			posiciones.append(pos)
	eleccion = menuEdificios(prints, ciudad, posiciones)
	return eleccion

def menuEdificios(prints, ciudad, posiciones):
	banner()
	for textoEdificio in prints:
		print(textoEdificio)

	eleccion = read(min=0, max=len(prints)-1)

	if eleccion == 0:
		return []
	posicion = posiciones[eleccion]
	nivelActual = int(ciudad['position'][posicion]['level'])
	if ciudad['position'][posicion]['isBusy']:
		nivelActual += 1

	banner()
	print(_('edificio:{}').format(ciudad['position'][posicion]['name']))
	print(_('nivel actual:{}').format(nivelActual))

	nivelFinal = read(min=nivelActual, msg=_('subir al nivel:'))

	niveles = nivelFinal - nivelActual
	rta = []
	for i in range(0, niveles):
		rta.append(posicion)
	return rta

def pedirValor(text, max):
	vals = list()
	for n in range(0, max+1):
		vals.append(str(n))
	vals.append('')
	var = read(msg=text, values=vals)
	if var == '':
		var = 0
	return int(var)

def getIdsDeCiudades(s, all=False):
	global ciudades
	global ids
	if ids is None or ciudades is None or s.padre is False:
		html = s.get()
		ciudades = re.search(r'relatedCityData:\sJSON\.parse\(\'(.+?),\\"additionalInfo', html).group(1) + '}'
		ciudades = ciudades.replace('\\', '')
		ciudades = ciudades.replace('city_', '')
		ciudades = json.loads(ciudades, strict=False)

		ids = [ciudad for ciudad in ciudades]
		ids = sorted(ids)

	# {'coords': '[x:y] ', 'id': idCiudad, 'tradegood': '..', 'name': 'nomberCiudad', 'relationship': 'ownCity'|'occupiedCities'|..}
	if all is False:
		ids_own   = [ciudad for ciudad in ciudades if ciudades[ciudad]['relationship'] == 'ownCity']
		ids_other = [ciudad for ciudad in ciudades if ciudades[ciudad]['relationship'] != 'ownCity']
		ciudades_own = ciudades.copy()
		for id in ids_other:
			del ciudades_own[id]
		return (ids_own, ciudades_own)
	else:
		return (ids, ciudades)

def getIdsdeIslas(s):
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	idsIslas = set()
	for idCiudad in idsCiudades:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		idIsla = ciudad['islandId']
		idsIslas.add(idIsla)
	return list(idsIslas)
