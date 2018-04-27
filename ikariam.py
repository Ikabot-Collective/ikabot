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
import sesion
import parser
import subirEdificio

ids = None
ciudades = None
infoUser = ''
cookieFile = '/tmp/.cookies.txt'
telegramFile = '.telegram.txt'
urlCiudad = 'view=city&cityId='
urlIsla = 'view=island&islandId='
prompt = ' >>  '
tipoDeBien = ['Madera', 'Vino', 'Marmol', 'Cristal', 'Azufre']
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

def clear():
	os.system('clear')

def banner():
	clear()
	bner = """
	`7MMF'  `7MM                       `7MM\"""Yp,                 mm    
	  MM      MM                         MM    Yb                 MM    
	  MM      MM  ,MP'   ,6"Yb.          MM    dP    ,pW"Wq.    mmMMmm  
	  MM      MM ;Y     8)   MM          MM\"""bg.   6W'   `Wb     MM    
	  MM      MM;Mm      ,pm9MM          MM    `Y   8M     M8     MM    
	  MM      MM `Mb.   8M   MM          MM    ,9   YA.   ,A9     MM    
	.JMML.  .JMML. YA.  `Moo9^Yo.      .JMMmmmd9     `Ybmd9'      `Mbmo
	"""
	print('\n{}\n\n{}\n'.format(bner, infoUser))

class bcolors:
	HEADER = '\033[95m'
	STONE = '\033[37m'
	BLUE = '\033[94m'
	GREEN = '\033[92m'
	WARNING = '\033[93m'
	RED = '\033[91m'
	BLACK = '\033[90m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

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

def enviarBienes(s, idCiudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az, barcos):
	s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudadOrigen, 'ajax': '1'}) 
	s.post(payloadPost={'action': 'transportOperations', 'function': 'loadTransportersWithFreight', 'destinationCityId': idCiudadDestino, 'islandId': idIsla, 'oldView': '', 'position': '', 'avatar2Name': '', 'city2Name': '', 'type': '', 'activeTab': '', 'premiumTransporter': '0', 'minusPlusValue': '500', 'cargo_resource': md, 'cargo_tradegood1': vn, 'cargo_tradegood2': mr, 'cargo_tradegood3': cr, 'cargo_tradegood4': az, 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': barcos, 'backgroundView': 'city', 'currentCityId': idCiudadOrigen, 'templateView': 'transport', 'currentTab': 'tabSendTransporter', 'actionRequest': s.token(), 'ajax': '1'})

def planearViajes(s, rutas):
	for ruta in rutas:
		(idciudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az) = ruta
		barcosTotales = getBarcosTotales(s)
		while (md + vn + mr + cr + az) > 0:
			barcosDisp = esperarLlegada(s)
			capacidad = barcosDisp * 500
			mdEnv = md if capacidad > md else capacidad
			capacidad -= mdEnv
			md -= mdEnv
			vnEnv = vn if capacidad > vn else capacidad
			capacidad -= vnEnv
			vn -= vnEnv
			mrEnv = mr if capacidad > mr else capacidad
			capacidad -= mrEnv
			mr -= mrEnv
			crEnv = cr if capacidad > cr else capacidad
			capacidad -= crEnv
			cr -= crEnv
			azEnv = az if capacidad > az else capacidad
			capacidad -= azEnv
			az -= azEnv
			cantEnviada = mdEnv + vnEnv + mrEnv + crEnv + azEnv
			barcos = int(math.ceil((Decimal(cantEnviada) / Decimal(500))))
			enviarBienes(s, idciudadOrigen, idCiudadDestino, idIsla, mdEnv, vnEnv, mrEnv, crEnv, azEnv, barcos)

def esperarLlegada(s):
	barcos = getBarcosDisponibles(s)
	while barcos == 0:
		html = s.get()
		idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
		posted = s.post(url)
		eventos = re.findall(r'"enddate":(\d+),"currentdate":(\d+)}', posted)
		esperaMinima = 10000000
		for evento in eventos:
			tiempoRestante = int(evento[0]) - int(evento[1])
			if tiempoRestante < esperaMinima:
				esperaMinima = tiempoRestante
		if eventos:
			time.sleep(esperaMinima)
		else:
			time.sleep(10 * 60)
		barcos = getBarcosDisponibles(s)
	return barcos

def getBarcosDisponibles(s):
	html = s.get()
	return int(re.search(r'GlobalMenu_freeTransporters">(\d+)<', html).group(1))

def getBarcosTotales(s):
	html = s.get()
	return int(re.search(r'maxTransporters">(\d+)<', html).group(1))

def getRescursosDisponibles(html, num=False):
	recursos = re.search(r'\\"resource\\":(\d+),\\"2\\":(\d+),\\"1\\":(\d+),\\"4\\":(\d+),\\"3\\":(\d+)}', html)
	if num:
		return [int(recursos.group(1)), int(recursos.group(3)), int(recursos.group(2)), int(recursos.group(5)), int(recursos.group(4))]
	else:
		return [recursos.group(1), recursos.group(3), recursos.group(2), recursos.group(5), recursos.group(4)]

def getCapacidadDeAlmacenamiento(html):
	return re.search(r'maxResources:\s*JSON\.parse\(\'{\\"resource\\":(\d+),', html).group(1)

def getConsumoDeVino(html):
	return int(re.search(r'GlobalMenu_WineConsumption"\s*class="rightText">\s*(\d*)\s', html).group(1))

def getProduccion(s, idCiudad):
	prod = s.post(payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudad, 'ajax': '1'}) 
	wood = Decimal(re.search(r'"resourceProduction":([\d|\.]+),', prod).group(1))
	good = Decimal(re.search(r'"tradegoodProduction":([\d|\.]+),', prod).group(1))
	typeGood = int(re.search(r'"producedTradegood":"([\d|\.]+)"', prod).group(1))
	return (wood, good, typeGood)

def pedirValor(text, max):
	vals = list()
	for n in range(0, max+1):
		vals.append(str(n))
	vals.append('')
	var = read(msg=text, values=vals)
	if var == '':
		var = 0
	return int(var)

def enviarVino(s):
	banner()
	vinoTotal = 0
	dict_idVino_diponible = {}
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	for idCiudad in idsCiudades:
		esVino =  ciudades[idCiudad]['tradegood'] == '1'
		if esVino:
			html = s.get(urlCiudad + idCiudad)
			recursos = getRescursosDisponibles(html)
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
			max = getRescursosDisponibles(htmlO)
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

def addPuntos(num):
	return '{0:,}'.format(int(num)).replace(',','.')

def diasHorasMinutos(segundosTotales):
	dias = int(segundosTotales / Decimal(86400))
	segundosTotales -= dias * Decimal(86400)
	horas = int(segundosTotales / Decimal(3600))
	segundosTotales -= horas * Decimal(3600)
	minutos = int(segundosTotales / Decimal(60))
	return (dias, horas, minutos)

def enter():
	getpass.getpass('\n[Enter]')

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

def sendToBot(s, msg, Token=False):
	if Token is False:
		msg = '{}\n{}'.format(infoUser, msg)
	with open(telegramFile, 'r') as filehandler:
		text = filehandler.read()
		(botToken, chatId) = text.splitlines()
		sesion.get('https://api.telegram.org/bot{}/sendMessage'.format(botToken), params={'chat_id': chatId, 'text': msg})

def botValido(s):
	with open(telegramFile, 'r') as filehandler:
		text = filehandler.read()
	rta = re.search(r'\d{6,}:[A-Za-z0-9_-]{34,}\n\d{8,9}', text)
	if rta is None:
		print('Debe proporcionar las credenciales válidas para comunicarse por telegram.')
		print('Se requiere del token del bot a utilizar y de su chat_id')
		print('El token se le proporciona al momento de crear el bot, para averiguar su chat_id, hablele por telegram a @get_id_bot')
		rta = read(msg='Porporcionará las credenciales ahora? [y/N]')
		if rta.lower() == 'y':
			botToken = read(msg='Token del bot:')
			chat_id = read(msg='Char_id:')
			with open(telegramFile, 'w') as filehandler:
				filehandler.write(botToken + '\n' + chat_id)
		else:
			return False
	rand = random.randint(1000, 9999)
	sendToBot(s, 'El token a ingresar es:{:d}'.format(rand), Token=True)
	print('Se envio un mensaje por telegram, lo recibió? [Y/n]')
	rta = read()
	if rta.lower() == 'n':
		with open(telegramFile, 'w') as file:
			pass
		print('Revíse las credenciales y vuelva a proveerlas.')
		enter()
		return False
	else:
		recibido = read(digit=True, msg='Ingrese el token recibido mediante telegram:')
		if rand != recibido:
			print('Token incorrecto')
			enter()
			return False
		else:
			print('El token es correcto.')
			return True

def botDonador(s):
	if botValido(s) is False:
		return
	print('¿Donar a aserraderos o a bienes de cambio? [a/b]')
	rta = read(values=['a', 'A', 'b', 'B'])
	tipo = 'resource' if rta.lower() == 'a' else 'tradegood'
	print('Se donará compulsivamente cada día.')
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = '\nDono todos los días\n'
	setInfoSignal(s, info)
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	ciudades_dict = {}
	for idCiudad in idsCiudades:
		html = s.get(urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		ciudades_dict[idCiudad] = ciudad['islandId']
	try:
		while True:
			for idCiudad in idsCiudades:
				html = s.get(urlCiudad + idCiudad)
				madera = getRescursosDisponibles(html)[0]
				idIsla = ciudades_dict[idCiudad]
				s.post(payloadPost={'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': madera, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})
			time.sleep(24*60*60)
	except:
		msg = 'Ya no se donará.\n{}'.format(traceback.format_exc())
		sendToBot(s, msg)
		s.logout()

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

def update(s):
	out = run('git pull').read().decode("utf-8") 
	if 'Already up' in out:
		print('\nEstá actualizado')
	else:
		clear()
		print('Actualizando...\n')
		print(out)
		print('Listo.')
		print('Reinicie el preceso para que los cambios surjan efecto.')
	enter()

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

def forkear(s):
	newpid = os.fork()
	if newpid != 0:
		# padre
		s.login()
		newpid = str(newpid)
		run('kill -SIGSTOP ' + newpid)
		run('bg ' + newpid)
		run('disown ' + newpid)
	else:
		# hijo
		s.padre = False

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

def create_handler(s):
	def _handler(signum, frame):
		raise Exception('Señal recibida número {:d}'.format(signum))
	return _handler

def setSignalsHandlers(s):
	signals = [signal.SIGHUP, signal.SIGQUIT, signal.SIGABRT, signal.SIGTERM]
	for sgn in signals:
		signal.signal(sgn, create_handler(s))

def setInfoSignal(s, info): # el proceso explica su funcion por stdout
	info = '{}\n{}'.format(s.urlBase, s.username) + info
	def _printInfo(signum, frame):
		print(info)
	signal.signal(signal.SIGUSR1, _printInfo) # kill -SIGUSR1 pid

def getSesion():
	global infoUser
	banner()
	html = sesion.get('https://es.ikariam.gameforge.com/?').text
	servidores = re.findall(r'<a href="(?:https:)?//(\w{2})\.ikariam\.gameforge\.com/\?kid=[\d\w-]*" target="_top" rel="nofollow" class="mmoflag mmo_\w{2}">(.+)</a>', html)
	i = 0
	for server in servidores:
		i += 1
		print('({:d}) {}'.format(i, server[1]))
	servidor = read(msg='Servidor:', min=1, max=len(servidores))
	srv = servidores[servidor - 1][0]
	infoUser = 'Servidor:{}'.format(servidores[servidor-1][1])
	banner()
	if srv != 'es':
		html = sesion.get('https://{}.ikariam.gameforge.com/?'.format(srv)).text
	html = re.search(r'registerServer[\s\S]*registerServerServerInfo', html).group()
	mundos = re.findall(r'mobileUrl="s(\d{1,2})-\w{2}\.ikariam\.gameforge\.com"\s*?cookieName=""\s*>\s*(\w+)\s*</option>', html)
	i = 0
	for mundo in mundos:
		i += 1
		print('({:d}) {}'.format(i, mundo[1]))
	mundo = read(msg='Mundo:', min=1, max=len(mundos))
	infoUser += ', Mundo:{}'.format(mundos[mundo - 1][1])
	urlBase = 'https://s{:d}-{}.ikariam.gameforge.com/index.php?'.format(mundo, srv)
	uni_url = 's{:d}-{}.ikariam.gameforge.com'.format(mundo, srv)
	banner()
	usuario = read(msg='Usuario:')
	password = getpass.getpass('Contraseña:')
	headers = {'Host': uni_url, 'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:54.0) Gecko/20100101 Firefox/54.0','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate, br', 'Content-Type':'application/x-www-form-urlencoded', 'Referer': urlBase}
	payload = {'uni_url': uni_url, 'name': usuario, 'password': password, 'pwat_uid': '', 'pwat_checksum': '' ,'startPageShown' : '1' , 'detectedDevice' : '1' , 'kid':''}
	infoUser += ', Jugador:{}'.format(usuario)
	return sesion.Sesion(urlBase, payload, headers)

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
