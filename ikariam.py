#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import json
import re
import math
from decimal import *
import getpass
import random
import subprocess
import signal
import traceback
from web.sesion import *
from sisop.varios import *
from sisop.signals import *
from subirEdificio import *
from bot.botDonador import *
from donar import *
from config import *
import getJson
from getStatus import *
import update
from pedirInfo import *

def enviarVino(s):
	banner()
	vinoTotal = 0
	dict_idVino_diponible = {}
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	for idCiudad in idsCiudades:
		esVino =  ciudades[idCiudad]['tradegood'] == '1'
		if esVino:
			html = s.get(urlCiudad + idCiudad)
			recursos = getRecursosDisponibles(html)
			dict_idVino_diponible[idCiudad] = int(recursos[1]) - 1000 # dejo 1000 por las dudas
			if dict_idVino_diponible[idCiudad] < 0:
				dict_idVino_diponible[idCiudad] = 0
			vinoTotal += dict_idVino_diponible[idCiudad]
	aEnviar = len(ciudades) - len(dict_idVino_diponible)
	vinoXciudad = int(vinoTotal / aEnviar)
	maximo = addPuntos(vinoXciudad)

	if vinoXciudad > 100000:
		maximo = maximo[:-6] + '00.000'
	elif vinoXciudad > 10000:
		maximo = maximo[:-5] + '0.000'
	elif vinoXciudad > 1000:
		maximo = maximo[:-3] + '000'
	elif vinoXciudad > 100:
		maximo = maximo[:-2] + '00'
	elif vinoXciudad > 10:
		maximo = maximo[:-1] + '0'
	print('Se puede enviar como máximo {} a cada ciudad'.format(maximo))
	cantidad = read(msg='¿Cuanto vino enviar a cada ciudad?:', min=0, max=vinoXciudad)

	print('\nPor enviar {} de vino a cada ciudad'.format(addPuntos(cantidad)))
	print('¿Proceder? [Y/n]')
	rta = read()
	if rta.lower() == 'n':
		return

	forkear(s)
	if s.padre is True:
		return

	rutas = []
	for idCiudadDestino in idsCiudades:
		noEsVino =  ciudades[idCiudadDestino]['tradegood'] != '1'
		if noEsVino:
			htmlD = s.get(urlCiudad + idCiudadDestino)
			ciudadD = getCiudad(htmlD)
			idIsla = ciudadD['islandId']
			faltante = cantidad
			for idCiudadOrigen in dict_idVino_diponible:
				if faltante == 0:
					break
				vinoDisponible = dict_idVino_diponible[idCiudadOrigen]
				for ruta in rutas:
					(origen, _, _, _, vn, _, _, _) = ruta
					if origen == idCiudadOrigen:
						vinoDisponible -= vn
				enviar = faltante if vinoDisponible > faltante else vinoDisponible
				faltante -= enviar
				ruta = (idCiudadOrigen, idCiudadDestino, idIsla, 0, enviar, 0, 0, 0)
				rutas.append(ruta)

	info = '\nEnviar vino\n'
	for ruta in rutas:
		(idciudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az) = ruta
		html = s.get(urlCiudad + idciudadOrigen)
		ciudadO = getCiudad(html)
		html = s.get(urlCiudad + idCiudadDestino)
		ciudadD = getCiudad(html)
		info = info + '{} -> {}\nVino: {}\n'.format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(vn))
	setInfoSignal(s, info)
	planearViajes(s, rutas)
	s.logout()

def menuRutaComercial(s):
	idCiudadOrigen = None
	rutas = []
	while True:
		if idCiudadOrigen is None:
			banner()
			print('Ciudad de origen:')
			idCiudadOrigen = getIdCiudad(s)
			htmlO = s.get(urlCiudad + idCiudadOrigen)
			ciudadO = getCiudad(htmlO)
			max = getRecursosDisponibles(htmlO)
			total = list(map(int, max))
		banner()
		print('Ciudad de destino')
		idCiudadDestino = getIdCiudad(s)
		if idCiudadOrigen == idCiudadDestino:
			continue
		htmlD = s.get(urlCiudad + idCiudadDestino)
		ciudadD = getCiudad(htmlD)
		idIsla = ciudadD['islandId']
		banner()
		print('Disponible:')
		resto = total
		for ruta in rutas:
			(origen, _, _, md, vn, mr, cr, az) = ruta
			if origen == idCiudadOrigen:
				resto = (resto[0] - md, resto[1] - vn, resto[2] - mr, resto[3] - cr, resto[4] - az)
		print('Madera {} Vino {} Marmol {} Cristal {} Azufre {}'.format(addPuntos(resto[0]), addPuntos(resto[1]), addPuntos(resto[2]), addPuntos(resto[3]), addPuntos(resto[4])))
		print('Enviar:')
		md = pedirValor('Madera: ', resto[0])
		vn = pedirValor('Vino:   ', resto[1])
		mr = pedirValor('Marmol: ', resto[2])
		cr = pedirValor('Cristal:', resto[3])
		az = pedirValor('Azufre: ', resto[4])
		if md + vn + mr + cr + az == 0:
			idCiudadOrigen = None
			continue
		banner()
		print('Por enviar de {} a {}'.format(ciudadO['cityName'], ciudadD['cityName']))
		enviado = ''
		if md:
			enviado += 'Madera:{} '.format(addPuntos(md))
		if vn:
			enviado += 'Vino:{} '.format(addPuntos(vn))
		if mr:
			enviado += 'Marmol:{} '.format(addPuntos(mr))
		if cr:
			enviado += 'Cristal:{} '.format(addPuntos(cr))
		if az:
			enviado += 'Azufre:{}'.format(addPuntos(az))
		print(enviado)
		print('¿Proceder? [Y/n]')
		rta = read()
		if rta.lower() == 'n':
			idCiudadOrigen = None
		else:
			ruta = (idCiudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az)
			rutas.append(ruta)
			print('¿Realizar otro envio? [y/N]')
			rta = read()
			otroViaje = rta.lower() == 'y'
			if otroViaje is True:
				print('¿Misma ciudad de origen? [Y/n]')
				rta = read()
				ciudadDistinta = rta.lower() == 'n'
				if ciudadDistinta is True:
					idCiudadOrigen = None
			else:
				break

	forkear(s)
	if s.padre is True:
		return

	info = '\nRuta comercial\n'
	for ruta in rutas:
		(idciudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az) = ruta
		html = s.get(urlCiudad + idciudadOrigen)
		ciudadO = getCiudad(html)
		html = s.get(urlCiudad + idCiudadDestino)
		ciudadD = getCiudad(html)
		info = info + '{} -> {}\nMadera: {} Vino: {} Marmol: {} Cristal: {} Azufre: {}\n'.format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(md), addPuntos(vn), addPuntos(mr), addPuntos(cr), addPuntos(az))

	setInfoSignal(s, info)
	planearViajes(s, rutas)
	s.logout()

def diasHorasMinutos(segundosTotales):
	dias = int(segundosTotales / Decimal(86400))
	segundosTotales -= dias * Decimal(86400)
	horas = int(segundosTotales / Decimal(3600))
	segundosTotales -= horas * Decimal(3600)
	minutos = int(segundosTotales / Decimal(60))
	return (dias, horas, minutos)

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

def alertarAtaques(s):
	if botValido(s) is False:
		return
	print('Se buscarán ataques cada 15 minutos.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nEspero por ataques cada 29 minutos\n'
	setInfoSignal(s, info)
	fueAvisado = False
	try:
		while True:
			html = s.get()
			idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
			url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
			posted = s.post(url)
			ataque = re.search(r'"military":{"link":.*?","cssclass":"normalalert"', posted)
			if ataque is not None and fueAvisado is False:
				msg = 'Te están por atacar !!'
				sendToBot(s, msg)
				fueAvisado = True
			elif ataque is None and fueAvisado is True:
				fueAvisado = False
			time.sleep(15*60)
	except:
		msg = 'Ya no se alertarán más ataques.\n{}'.format(traceback.format_exc())
		sendToBot(s, msg)
		s.logout()

def entrarDiariamente(s):
	if botValido(s) is False:
		return
	print('Se entrará todos los días automaticamente.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nEntro diariamente\n'
	setInfoSignal(s, info)
	try:
		while True:
			s.get()
			time.sleep(24*60*60)
	except:
		msg = 'Ya no se entrará todos los días.\n{}'.format(traceback.format_exc())
		sendToBot(s, msg)
		s.logout()

def menu(s):
	banner()
	menu_actions = [subirEdificios, menuRutaComercial, enviarVino, getStatus, donar, buscarEspacios, entrarDiariamente, alertarAtaques, botDonador, update]
	mnu="""
(0) Salir
(1) Lista de construcción
(2) Enviar recursos
(3) Enviar vino
(4) Estado de la cuenta
(5) Donar
(6) Buscar espacios nuevos
(7) Entrar diariamente
(8) Alertar ataques
(9) Bot donador
(10) Actualizar IkaBot"""
	print(mnu)
	entradas = len(menu_actions)
	eleccion = read(min=0, max=entradas)
	if eleccion != 0:
		try:
			menu_actions[eleccion - 1](s)
		except KeyboardInterrupt:
			pass
		menu(s)
	else:
		clear()

def inicializar():
	path = os.path.abspath(__file__)
	path = os.path.dirname(path)
	os.chdir(path)
	run('touch ' + cookieFile)
	run('touch ' + telegramFile)

def main():
	inicializar()
	s = getSesion()
	setSignalsHandlers(s)
	try:
		menu(s)
	except:
		raise
	finally:
		if os.fork() == 0:
			s.logout()

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		clear()
