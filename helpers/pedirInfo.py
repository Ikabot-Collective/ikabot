#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import json
from config import *
from decimal import *
from helpers.getJson import getCiudad
from helpers.gui import banner

getcontext().prec = 30

def read(min=None, max=None, digit=False, msg=prompt, values=None): # lee input del usuario
	def _invalido():
		sys.stdout.write('\033[F\r') # Cursor up one line
		blank = ' ' * len(str(leido) + msg)
		sys.stdout.write('\r' + blank + '\r')
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

def getIdCiudad(s):
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
	for unId in ids:
		i += 1
		tradegood = ciudades[unId]['tradegood']
		bien = bienes[tradegood]
		nombre = ciudades[unId]['name']
		num = ' ' + str(i) if i < 10 else str(i)
		print('{}: {}{}{}'.format(num, nombre, pad(nombre), bien))
	eleccion = read(min=1, max=i)
	eleccion = int(eleccion) - 1
	return ids[eleccion]

def getEdificios(s, idCiudad):
	html = s.get(urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	i = 0
	pos = -1
	prints = []
	posiciones = []
	prints.append('(0)\t\tsalir')
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
			prints.append('(' + str(i) + ')' + '\tlv:' + level + '\t' + posicion['name'])
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
	print('edificio:{}'.format(ciudad['position'][posicion]['name']))
	print('nivel actual:{}'.format(nivelActual))

	nivelFinal = read(min=nivelActual, msg='subir al nivel:')

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

def getIdsDeCiudades(s):
	global ciudades
	global ids
	if ids is None or ciudades is None:
		html = s.get()
		ciudades = re.search(r'relatedCityData:\sJSON\.parse\(\'(.+?),\\"additionalInfo', html).group(1) + '}'
		ciudades = ciudades.replace('\\', '')
		ciudades = ciudades.replace('city_', '')
		ciudades = json.loads(ciudades, strict=False)
		ids = []
		for ciudad in ciudades:
			ids.append(ciudad)
	ids = sorted(ids)
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
