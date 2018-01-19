#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
try:
	import requests
except:
	sys.exit('Debe instalar el modulo de requests:\nsudo pip install requests')
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

cookieFile = '/tmp/.cookies.txt'
path = re.search(r'(.*/).*', sys.argv[0]).group(1)
telegramFile = path + '.telegram.txt'
urlCiudad = 'view=city&cityId='
urlIsla = 'view=island&islandId='
prompt = ' >>  '
tipoDeBien = ['Madera', 'Vino', 'Marmol', 'Cristal', 'Azufre']
getcontext().prec = 30

class Sesion:
	def __init__(self, urlBase, payload, headers):
		self.urlBase = urlBase
		self.payload = payload
		self.username = payload['name']
		self.headers = headers
		self.getCookie()

	def token(self):
		html = self.get()
		return re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)

	def updateCookieFile(self, primero=False, salida=False, nuevo=False, vencimiento=False):
		if primero is True:
			cookie_dict = dict(self.s.cookies.items())
			entrada = self.username + ' 1 ' + cookie_dict['PHPSESSID'] + ' ' + cookie_dict['ikariam'] + ' ' + self.urlBase + '\n'
			with open(cookieFile, 'a') as filehandler:
				filehandler.write(entrada)
		else:
			(fileInfo, text) = getFileInfo(self.username, self.urlBase)
			if fileInfo is None:
				if nuevo is True:
					raise ValueError('No se encontro linea en el cookieFile', text)
				else:
					return
			oldline = fileInfo.group(0)
			sesionesActivas = int(fileInfo.group(1))
			lines = text.splitlines()
			if salida is True:
				html = self.get()
			with open(cookieFile, 'w') as filehandler:
				for line in lines:
					if line != oldline:
						filehandler.write(line + '\n')
					else:
						if salida is True:
							if sesionesActivas > 1:
								newline = self.username + ' ' + str(sesionesActivas - 1) + ' ' + fileInfo.group(2) + ' ' + fileInfo.group(3) + ' ' + self.urlBase + '\n'
								filehandler.write(newline)
							else:
								idCiudad = getCiudad(html)['id']
								token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
								urlLogout = 'action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}'.format(idCiudad, token)
								self.s.get(self.urlBase + urlLogout, headers=self.headers)
						if nuevo is True:
							newline = self.username + ' ' + str(sesionesActivas + 1) + ' ' + fileInfo.group(2) + ' ' + fileInfo.group(3) + ' ' + self.urlBase + '\n'
							filehandler.write(newline)
						if vencimiento is True:
							pass

	def getCookie(self):
		fileInfo = getFileInfo(self.username, self.urlBase)[0]
		if fileInfo is None:
			self.login()
		else:
			cookie_dict = {'PHPSESSID': fileInfo.group(2), 'ikariam': fileInfo.group(3), 'ikariam_loginMode': '0'}
			self.s = requests.Session()
			requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
			self.updateCookieFile(nuevo=True)

	def login(self):
		self.s = requests.Session() # s es la sesion de conexion
		login = self.s.post(self.urlBase + 'action=loginAvatar&function=login', data=self.payload, headers=self.headers).text
		expired = re.search(r'index\.php\?logout', login)
		if expired is not None:
			sys.exit('Usuario o contrasenia incorrecta')
		self.updateCookieFile(primero=True)

	def expiroLaSesion(self):
		self.updateCookieFile(vencimiento=True) # borra la entrada vieja del CookieFile
		self.login()

	def checkCookie(self):
		sigueActiva = sesionActiva(self.username, self.urlBase, cookies=self.s.cookies)
		if sigueActiva is False:
			self.getCookie()

	def get(self, url=None):
		self.checkCookie()
		url = url or self.urlBase
		while True:
			try:
				html = self.s.get(url, headers=self.headers).text
				expired = re.search(r'index\.php\?logout', html)
				assert expired is None
				return html
			except:
				self.expiroLaSesion()

	def post(self, url, payloadPost=None):
		self.checkCookie()
		payloadPost = payloadPost or {}
		while True:
			try:
				html = self.s.post(url, data=payloadPost, headers=self.headers).text
				expired = re.search(r'index\.php\?logout', html)
				assert expired is None
				return html
			except:
				self.expiroLaSesion()

	def bye(self):
		self.updateCookieFile(salida=True)
		os._exit(0)

def read(min=None, max=None, digit=False, msg=prompt): # lee input del usuario
	def _invalido():
		sys.stdout.write("\033[F\r") # Cursor up one line
		blank = ' ' * len(str(leido) + msg)
		sys.stdout.write(blank + "\r")
		return read(min, max, digit, msg)

	leido = input(msg)

	if digit is True or min is not None or max is not None:
		if leido.isdigit() is False:
			return _invalido()
		else:
			while True:
				try:
					leido = eval(leido)
					break
				except:
					return _invalido()
	if min is not None and leido < min:
			return _invalido()
	if max is not None and leido > max:
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
	print('\n{}\n'.format(bner))

def getFileInfo(username, urlBase):
	with open(cookieFile, 'r') as filehandler:
		text = filehandler.read()
	regex =  re.escape(username) + r'\s(\d+)\s(.*?)\s(.*?)\s' + re.escape(urlBase)
	return (re.search(regex, text), text)

def sesionActiva(username, urlBase, cookies=None):
	fileInfo = getFileInfo(username, urlBase)[0]
	if fileInfo is None:
		return False
	if cookies is not None:
		return fileInfo.group(2) == cookies['PHPSESSID']
	return True

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

def borrar(texto, ocurrencias):
	for ocurrencia in ocurrencias:
		texto = texto.replace(ocurrencia, '')
	return texto


def getIsla(html):
	isla = re.search(r'\[\["updateBackgroundData",([\s\S]*?),"specialServerBadges', html).group(1) + '}'

	isla = isla.replace('buildplace', 'empty')
	isla = isla.replace('xCoord', 'x')
	isla = isla.replace('yCoord', 'y')
	isla = isla.replace(',"owner', ',"')
	isla = isla.replace(',"tradegoodLevel',',"goodLv')
	isla = isla.replace(',"tradegood', ',"good')
	isla = isla.replace(',"resourceLevel', ',"woodLv')
	isla = isla.replace(',"wonderLevel', ',"wonderLv')
	isla = isla.replace('avatarScores', 'scores')

	remove = []

	sub = re.search(r'(,"wonderName":".+?),"cities', isla)
	remove.append(sub.group(1))

	sub = re.search(r',"type":\d', isla)
	remove.append(sub.group())

	quitar = re.search(r'(,"barbarians[\s\S]*?),"scores"', isla).group(1)

	remove.append(quitar)
	remove.append(',"goodTarget":"tradegood"')
	remove.append(',"name":"Building ground"')
	remove.append(',"name":"Terreno"')
	remove.append(',"actions":[]')
	remove.append('"id":-1,')
	remove.append(',"level":0,"viewAble":1')
	remove.append(',"empty_type":"normal"')
	remove.append(',"empty_type":"premium"')
	remove.append(',"hasTreaties":0')
	remove.append(',"hasTreaties":1')
	remove.append(',"infestedByPlague":false')
	remove.append(',"infestedByPlague":true')
	remove.append(',"viewAble":0')
	remove.append(',"viewAble":1')
	remove.append(',"viewAble":2')
	isla = borrar(isla, remove)

	return json.loads(isla, strict=False)

def getCiudad(html):
	ciudad = re.search(r'"updateBackgroundData",([\s\S]*?),"(?:beachboys|spiesInside)', html).group(1) + '}'

	ciudad = ciudad.replace(',"owner', ',"')
	ciudad = ciudad.replace('islandXCoord','x')
	ciudad = ciudad.replace('islandYCoord','y')
	ciudad = '{"cityName"' + ciudad[len('{"name"'):]

	remove = []

	sub = re.search(r',"buildingSpeedupActive":\d', ciudad)
	remove.append(sub.group())

	sub = re.search(r',"showPirateFortressBackground":\d', ciudad)
	remove.append(sub.group())

	sub = re.search(r',"showPirateFortressShip":\d', ciudad)
	remove.append(sub.group())

	ciudad = borrar(ciudad, remove)

	for elem in ['sea', 'land', 'shore', 'wall']:
		ciudad = ciudad.replace('"building":"buildingGround {}"'.format(elem),'"name":"empty"')
	ciudad = ciudad.replace('"isBusy":true,','"isBusy":false,')

	ampliando = re.findall(r'(("name":"[\w\s\\]*","level":"\d*","isBusy":false,"canUpgrade":\w*,"isMaxLevel":\w*,"building":"\w*?)\sconstructionSite","(?:completed|countdownText|buildingimg).*?)}',ciudad)
	for edificio in ampliando:
		viejo = edificio[1]+'"'
		nuevo = viejo.replace('"isBusy":false,', '"isBusy":true,')
		ciudad = ciudad.replace(edificio[0], nuevo)

	return json.loads(ciudad, strict=False)

def getTiempoDeConstruccion(html):
	fin = re.search(r'"endUpgradeTime":(\d{10})', html)
	if fin is None:
		return 0
	inicio = re.search(r'serverTime:\s"(\d{10})', html)
	espera = int(fin.group(1)) - int(inicio.group(1))
	if espera < 0:
		espera = 5
	return espera

def esperarConstruccion(s, idCiudad):
	slp = 1
	while slp > 0:
		html = s.get(s.urlBase + urlCiudad + idCiudad)
		slp = getTiempoDeConstruccion(html)
		time.sleep(slp + 5)
	return getCiudad(html)

def subirEdificio(s, idCiudad, posicion):
	ciudad = esperarConstruccion(s, idCiudad)
	edificio = ciudad['position'][posicion]

	if edificio['isMaxLevel'] is True or edificio['canUpgrade'] is False:
		return

	url = s.urlBase + 'action=CityScreen&function=upgradeBuilding&actionRequest={}&cityId={}&position={:d}&level={}&backgroundView=city&templateView={}&ajax=1'.format(s.token(), idCiudad, posicion, edificio['level'], edificio['building'])
	s.post(url)

def subirEdificios(s):
	banner()
	idCiudad = getIdCiudad(s)
	edificios = getEdificios(s, idCiudad)
	if edificios == []:
		return
	esPadre = forkear(s)
	if esPadre is True:
		return

	info = '\nSubir edificio\n'
	html = s.get(s.urlBase + urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	info = info + 'Ciudad: {}\nEdificio: {}'.format(ciudad['cityName'], ciudad['position'][edificios[0]]['name'])

	setInfoSignal(s, info)
	for edificio in edificios:
		subirEdificio(s, idCiudad, edificio)
	s.bye()

def getIdsDeCiudades(s):
	html = s.get()
	ciudades = re.search(r'relatedCityData:\sJSON\.parse\(\'(.+?),\\"additionalInfo', html).group(1) + '}'
	ciudades = ciudades.replace('\\', '')
	ciudades = ciudades.replace('city_', '')
	ciudades = json.loads(ciudades, strict=False)
	ids = []
	for ciudad in ciudades:
		ids.append(ciudad)
	return (sorted(ids), ciudades)

def getIdCiudad(s):
	(ids, ciudades) = getIdsDeCiudades(s)
	bienes = {'1': '(V)', '2': '(M)', '3': '(C)', '4': '(A)'}
	prints = []
	i = 0
	for unId in ids:
		i += 1
		tradegood = ciudades[unId]['tradegood']
		bien = bienes[tradegood]
		prints.append(str(i) + ': ' + ciudades[unId]['name'] + ' \t' + bien)
	eleccion = menuCiudades(prints)
	return ids[int(eleccion) - 1]

def menuCiudades(ciudades):
	for textoCiudad in ciudades:
		print(textoCiudad)
	return read(min=1, max=len(ciudades))

def getEdificios(s, idCiudad):
	html = s.get(s.urlBase + urlCiudad + idCiudad)
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
	posicion = posiciones[eleccion]
	if eleccion == 0:
		return []

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
	s.post(s.urlBase, payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudadOrigen, 'ajax': '1'}) 
	s.post(s.urlBase, payloadPost={'action': 'transportOperations', 'function': 'loadTransportersWithFreight', 'destinationCityId': idCiudadDestino, 'islandId': idIsla, 'oldView': '', 'position': '', 'avatar2Name': '', 'city2Name': '', 'type': '', 'activeTab': '', 'premiumTransporter': '0', 'minusPlusValue': '500', 'cargo_resource': md, 'cargo_tradegood1': vn, 'cargo_tradegood2': mr, 'cargo_tradegood3': cr, 'cargo_tradegood4': az, 'capacity': '5', 'max_capacity': '5', 'jetPropulsion': '0', 'transporters': barcos, 'backgroundView': 'city', 'currentCityId': idCiudadOrigen, 'templateView': 'transport', 'currentTab': 'tabSendTransporter', 'actionRequest': s.token(), 'ajax': '1'})

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
		url = s.urlBase + 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
		posted = s.post(url)
		eventos = re.findall(r'"enddate":(\d+),"currentdate":(\d+)}', posted)
		esperaMinima = 10000000
		for evento in eventos:
			tiempoRestante = int(evento[0]) - int(evento[1])
			if tiempoRestante < esperaMinima:
				esperaMinima = tiempoRestante
		if eventos:
			time.sleep(esperaMinima)
		barcos = getBarcosDisponibles(s)
	return barcos

def getBarcosDisponibles(s):
	html = s.get()
	return int(re.search(r'GlobalMenu_freeTransporters">(\d+)<', html).group(1))

def getBarcosTotales(s):
	html = s.get()
	return int(re.search(r'maxTransporters">(\d+)<', html).group(1))

def getRescursosDisponibles(html):
	recursos = re.search(r'\\"resource\\":(\d+),\\"2\\":(\d+),\\"1\\":(\d+),\\"4\\":(\d+),\\"3\\":(\d+)}', html)
	return [recursos.group(1), recursos.group(3), recursos.group(2), recursos.group(5), recursos.group(4)]

def getCapacidadDeAlmacenamiento(html):
	return re.search(r'maxResources:\s*JSON\.parse\(\'{\\"resource\\":(\d+),', html).group(1)

def getConsumoDeVino(html):
	return int(re.search(r'GlobalMenu_WineConsumption"\s*class="rightText">\s*(\d*)\s', html).group(1))

def getProduccion(s, idCiudad):
	prod = s.post(s.urlBase, payloadPost={'action': 'header', 'function': 'changeCurrentCity', 'actionRequest': s.token(), 'cityId': idCiudad, 'ajax': '1'}) 
	wood = Decimal(re.search(r'"resourceProduction":([\d|\.]+),', prod).group(1))
	good = Decimal(re.search(r'"tradegoodProduction":([\d|\.]+),', prod).group(1))
	typeGood = int(re.search(r'"producedTradegood":"([\d|\.]+)"', prod).group(1))
	return (wood, good, typeGood)

def pedirValor(text, max):
	var = read(msg=text)
	while (var.isdigit is False and var != '') or (var.isdigit is True and int(var) > max):
		var = read(msg=text)
	if var == '':
		var = 0
	return int(var)

def menuRutaComercial(s):
	banner()
	print('Ciudad de origen:')
	idCiudadOrigen = getIdCiudad(s)
	htmlO = s.get(s.urlBase + urlCiudad + idCiudadOrigen)
	ciudadO = getCiudad(htmlO)
	max = getRescursosDisponibles(htmlO)
	disponible = [int(max[0]), int(max[1]), int(max[2]), int(max[3]), int(max[4])]

	rutas = []
	while True:
		banner()
		print('\nCiudad de destino')
		idCiudadDestino = getIdCiudad(s)
		if idCiudadOrigen == idCiudadDestino:
			continue
		htmlD = s.get(s.urlBase + urlCiudad + idCiudadDestino)
		ciudadD = getCiudad(htmlD)
		idIsla = re.search(r'"islandId":"(\d+)"', htmlD).group(1)
		banner()
		print('Disponible:')
		print('Madera ' + addPuntos(disponible[0]) + ' Vino ' + addPuntos(disponible[1]) + ' Marmol ' + addPuntos(disponible[2]) + ' Cristal ' + addPuntos(disponible[3]) + ' Azufre ' + addPuntos(disponible[4]))
		print('Enviar:')
		md = pedirValor('Madera: ', disponible[0])
		vn = pedirValor('Vino:   ', disponible[1])
		mr = pedirValor('Marmol: ', disponible[2])
		cr = pedirValor('Cristal:', disponible[3])
		az = pedirValor('Azufre: ', disponible[4])
		banner()
		print('Por enviar de {} a {}\nMadera {} Vino {} Marmol {} Cristal {} Azufre {}'.format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(md), addPuntos(vn), addPuntos(mr), addPuntos(cr), addPuntos(az)))
		print('¿Proceder? [Y/n]')
		rta = read()
		if rta.lower() == 'n':
			continue
		disponible[0] -= md
		disponible[1] -= vn
		disponible[2] -= mr
		disponible[3] -= cr
		disponible[4] -= az
		ruta = (idCiudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az)
		rutas.append(ruta)
		print('¿Realizar otro envio? [y/N]')
		rta = read()
		otroViaje = rta.lower() == 'y'
		if otroViaje is True:
			print('¿Misma ciudad de origen? [Y/n]')
			rta = read()
			mismaCiudad = rta == '' or rta.lower() == 'y'
			if mismaCiudad is False:
				banner()
				print('Ciudad de origen:')
				idCiudadOrigen = getIdCiudad(s)
				htmlO = s.get(s.urlBase + urlCiudad + idCiudadOrigen)
				ciudadO = getCiudad(htmlO)
				max = getRescursosDisponibles(htmlO)
				disponible = [int(max[0]), int(max[1]), int(max[2]), int(max[3]), int(max[4])]
		else:
			break
	esPadre = forkear(s)
	if esPadre is True:
		return

	info = '\nRuta comercial\n'
	for ruta in rutas:
		(idciudadOrigen, idCiudadDestino, idIsla, md, vn, mr, cr, az) = ruta
		html = s.get(s.urlBase + urlCiudad + idciudadOrigen)
		ciudadO = getCiudad(html)
		html = s.get(s.urlBase + urlCiudad + idCiudadDestino)
		ciudadD = getCiudad(html)
		info = info + '{} -> {}\nMadera: {} Vino: {} Marmol: {} Cristal: {} Azufre: {}\n'.format(ciudadO['cityName'], ciudadD['cityName'], addPuntos(md), addPuntos(vn), addPuntos(mr), addPuntos(cr), addPuntos(az))

	setInfoSignal(s, info)
	planearViajes(s, rutas)
	s.bye()

def addPuntos(num):
	return '{0:,}'.format(int(num)).replace(',','.')

def diasHorasMinutos(segundosTotales):
	dias = int(segundosTotales / Decimal(86400))
	segundosTotales -= dias * Decimal(86400)
	horas = int(segundosTotales / Decimal(3600))
	segundosTotales -= horas * Decimal(3600)
	minutos = int(segundosTotales / Decimal(60))
	return (dias, horas, minutos)

def getStatus(s):
	banner()
	tipoCiudad = [bcolors.ENDC, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]
	html = s.get()
	ids = re.findall(r'city_(\d+)', html)
	ids = set(ids)
	ids = sorted(ids)
	print('Barcos {:d}/{:d}'.format(getBarcosDisponibles(s), getBarcosTotales(s)))
	for unId in ids:
		html = s.get(s.urlBase + urlCiudad + unId)
		ciudad = getCiudad(html)
		(wood, good, typeGood) = getProduccion(s, unId)
		print('\033[1m' + tipoCiudad[int(typeGood)] + ciudad['cityName'] + tipoCiudad[0])
		max = getRescursosDisponibles(html)
		capacidadDeAlmacenamiento = getCapacidadDeAlmacenamiento(html)
		crecursos = []
		for i in range(0,5):
			if max[i] == capacidadDeAlmacenamiento:
				crecursos.append(bcolors.RED)
			else:
				crecursos.append(bcolors.ENDC)
		print('Almacenamiento:')
		print(addPuntos(capacidadDeAlmacenamiento))
		print('Recursos:')
		print('Madera {1}{2}{0} Vino {3}{4}{0} Marmol {5}{6}{0} Cristal {7}{8}{0} Azufre {9}{10}{0}'.format(bcolors.ENDC, crecursos[0], addPuntos(max[0]), crecursos[1], addPuntos(max[1]), crecursos[2], addPuntos(max[2]), crecursos[3], addPuntos(max[3]), crecursos[4], addPuntos(max[4])))
		consumoXhr = getConsumoDeVino(html)
		tipo = tipoDeBien[typeGood]
		print('Producción:')
		print('Madera:{} {}:{}'.format(addPuntos(wood*3600), tipo, addPuntos(good*3600)))
		if consumoXhr == 0:
			print('{}{}No se consume vino!{}'.format(bcolors.RED, bcolors.BOLD, bcolors.ENDC))
		elif typeGood == 1 and (good*3600) > consumoXhr:
			print('Hay vino para:\n∞')
		else:
			consumoXseg = Decimal(consumoXhr) / Decimal(3600)
			segsRestantes = Decimal(int(max[1])) / Decimal(consumoXseg)
			(dias, horas, minutos) = diasHorasMinutos(segsRestantes)
			texto = ''
			if dias > 0:
				texto = str(dias) + 'D '
			if horas > 0:
				texto = texto + str(horas) + 'H '
			if minutos > 0 and dias == 0:
				texto = texto + str(minutos) + 'M '
			print('Hay vino para:\n{}'.format(texto))
		for edificio in ciudad['position']:
			if edificio['name'] == 'empty':
				continue
			if edificio['isMaxLevel'] is True:
				color = bcolors.BLACK
			elif edificio['canUpgrade'] is True:
				color = bcolors.GREEN
			else:
				color = bcolors.RED
			level = edificio['level']
			if int(level) < 10:
				level = ' ' + level
			if edificio['isBusy'] is True:
				level = level + '+'
			print('lv:{}\t{}{}{}'.format(level, color, edificio['name'], bcolors.ENDC))
		getpass.getpass('\n[Enter]')
		print('')

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
		print('{}: Se encuentra en ampliación\n'.format(bien))
	return infoMina is not None

def donar(s):
	bienes = {'1': 'Viñedo', '2': 'Cantera', '3': 'Mina de cristal', '4': 'Mina de azufre'}
	banner()

	idCiudad = getIdCiudad(s)
	html = s.get(s.urlBase + urlCiudad + idCiudad)
	ciudad = getCiudad(html)
	banner()

	madera = getRescursosDisponibles(html)[0]
	almacenamiento = getCapacidadDeAlmacenamiento(html)

	idIsla = ciudad['islandId']
	html = s.get(s.urlBase + urlIsla + idIsla)
	isla = getIsla(html)
	print(str(len(isla['cities'])))
	print(str(isla))
	read()

	tipo = re.search(r'"tradegood":"(\d)"', html).group(1)
	bien = bienes[tipo]

	urlAserradero = s.urlBase + 'view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1'.format(idIsla, s.token())
	aserraderoOk = printEstadoMina(s, urlAserradero, 'Aserradero')

	urlBien = s.urlBase + 'view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest={2}&ajax=1'.format(tipo, idIsla, s.token())
	bienOk = printEstadoMina(s, urlBien, bien)

	tipo = ['resource', 'tradegood']
	print('Madera disopnible:{} / {}\n'.format(addPuntos(madera), addPuntos(almacenamiento)))

	if aserraderoOk is True and bienOk is True:
		msg = 'Aserradero(1) o ' + bien + '(2)?:'
		tipoDonacion = read()(msg=msg)
		while tipoDonacion != '1' and tipoDonacion != '2':
			tipoDonacion = read()(msg=msg)
	elif aserraderoOk is True and bienOk is False:
		tipoDonacion = '1'
		print('Aserradero:\n')
	elif aserraderoOk is False and bienOk is True:
		tiptipoDonaciono = '2'
		print('{}:\n'.format(bien))
	else:
		print('No se puede donar\n')
		return

	tipo = tipo[int(tipoDonacion) - 1]

	cantidad = read(min=0, max=int(madera), msg='Cantidad:')
	s.post(s.urlBase, {'islandId': idIsla, 'type': tipo, 'action': 'IslandScreen', 'function': 'donate', 'donation': cantidad, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': s.token(), 'ajax': '1'})

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

def forkear(s):
	newpid = os.fork()
	if newpid != 0:
		esPadre = True
		s.updateCookieFile(nuevo=True)
		newpid = str(newpid)
		run('kill -SIGSTOP ' + newpid)
		run('bg ' + newpid)
		run('disown ' + newpid)
	else:
		esPadre = False
	return esPadre

def getIdsdeIslas(s):
	(idsCiudades, ciudades) = getIdsDeCiudades(s)
	idsIslas = set()
	for idCiudad in idsCiudades:
		html = s.get(s.urlBase + urlCiudad + idCiudad)
		ciudad = getCiudad(html)
		idIsla = ciudad['islandId']
		idsIslas.add(idIsla)
	return list(idsIslas)

def sendToBot(msg):
	with open(telegramFile, 'r') as filehandler:
		text = filehandler.read()
		(botToken, chatId) = text.splitlines()
		requests.get('https://api.telegram.org/bot{}/sendMessage'.format(botToken), params={ "chat_id": chatId, "text": msg })

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
	sendToBot('El token a ingresar es:{:d}'.format(rand))
	print('Se envio un mensaje por telegram, lo recibió? [Y/n]')
	rta = read()
	if rta.lower() == 'n':
		with open(telegramFile, 'w') as file:
			pass
		print('Revíse las credenciales y vuelva a proveerlas.')
		read(msg='[Enter]')
		return False
	else:
		recibido = read(digit=True, msg='Ingrese el token recibido mediante telegram:')
		if rand != recibido:
			print('Token incorrecto')
			read(msg='[Enter]')
			return False
		else:
			print('El token es correcto.')
			return True

def buscarEspacios(s):
	if botValido(s) is False:
		return
	print('Se buscarán espacios nuevos cada hora.')
	read(msg='[Enter]')
	esPadre = forkear(s)
	if esPadre is True:
		return
	info = '\nBusco espacios nuevos en las islas cada 1 hora\n'
	setInfoSignal(s, info)
	idIslas = getIdsdeIslas(s)
	espacios_dict = {}
	while True:
		for idIsla in idIslas:
			html = s.get(s.urlBase + urlIsla + idIsla)
			isla = getIsla(html)
			espacios = 0
			for city in isla['cities']:
				if city['type'] == 'empty':
					espacios += 1
			if idIsla in espacios_dict:
				if espacios_dict[idIsla] < espacios:
					msg = 'Alguien desaparecio en {} {}:{} {}'.format(tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
					sendToBot(msg)
				if espacios_dict[idIsla] > espacios:
					msg = 'Alguien fundó en {} {}:{} {}'.format(tipoDeBien[int(isla['good'])], isla['x'], isla['y'], isla['name'])
					sendToBot(msg)
			espacios_dict[idIsla] = espacios
		time.sleep(1*60*60)
	s.bye()

def alertarAtaques(s):
	if botValido(s) is False:
		return
	print('Se buscarán ataques cada 15 minutos.')
	read(msg='[Enter]')
	esPadre = forkear(s)
	if esPadre is True:
		return
	info = '\nEspero por ataques cada 29 minutos\n'
	setInfoSignal(s, info)
	fueAvisado = False
	while True:
		html = s.get()
		idCiudad = re.search(r'currentCityId:\s(\d+),', html).group(1)
		url = s.urlBase + 'view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(idCiudad, s.token())
		posted = s.post(url)
		ataque = re.search(r'"military":{"link":.*?","cssclass":"normalalert"', posted)
		if ataque is not None and fueAvisado is False:
			msg = 'Estan por atacar a la cuenta {} !!'.format(s.username)
			sendToBot(msg)
			fueAvisado = True
		elif ataque is None and fueAvisado is True:
			fueAvisado = False
		time.sleep(15*60)
	s.bye()

def entrarDiariamente(s):
	print('Se entrará todos los días automaticamente.')
	read(msg='[Enter]')
	esPadre = forkear(s)
	if esPadre is True:
		return
	info = '\nEntro diariamente\n'
	setInfoSignal(s, info)
	while True:
		s.get()
		time.sleep(24*60*60)
	s.bye()

def menu(s):
	banner()
	mnu="""
(0) Salir
(1) Lista de construcción
(2) Enviar recursos
(3) Estado de la cuenta
(4) Donar
(5) Buscar espacios nuevos
(6) Entrar diariamente
(7) Alertar ataques"""
	print(mnu)
	eleccion = read(min=0, max=7)
	if eleccion != 0:
		menu_actions[eleccion](s)
		menu(s)
	else:
		clear()

menu_actions = {
	1: subirEdificios,
	2: menuRutaComercial,
	3: getStatus,
	4: donar,
	5: buscarEspacios,
	6: entrarDiariamente,
	7: alertarAtaques
}

def checkFile(): # si no existe lo creo
	run('touch ' + cookieFile)
	run('touch ' + telegramFile)

def create_handler(s):
	def _handler(signum, frame):
		s.updateCookieFile(salida=True)
		signal.signal(signum, signal.SIG_DFL)
		os.kill(os.getpid(), signum) # Rethrow signal, this time without catching it
	return _handler

def setSignalsHandlers(s):
	signals = [signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGABRT, signal.SIGTERM]
	for sgn in signals:
		signal.signal(sgn, create_handler(s))

def setInfoSignal(s, info): # el proceso explica su funcion por stdout
	info = '{}\n{}'.format(s.urlBase, s.username) + info
	def _printInfo(signum, frame):
		print(info)
	signal.signal(signal.SIGUSR1, _printInfo) # kill -SIGUSR1 pid

def getSesion():
	banner()
	servidores = ['ar', 'br', 'es', 'fr', 'it', 'mx', 'pt', 'us', 'en']
	i = 0
	for srv in servidores:
		i += 1
		print('({:d}) .{}'.format(i, srv))
	servidor = read(msg='Servidor:', min=1, max=len(servidores))
	servidor = servidores[servidor-1]
	banner()
	mundos = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Pi', 'Rho', 'Demeter', 'Dionysos', 'Eirene', 'Eunomia', 'Gaia', 'Hades', 'Hephaistos']
	i = 0
	for mundo in mundos:
		i += 1
		print('({:d}) {}'.format(i, mundo))
	mundo = read(msg='Mundo:', min=1, max=len(mundos))
	urlBase = 'https://s{:d}-{}.ikariam.gameforge.com/index.php?'.format(mundo, servidor)
	uni_url = re.search(r'https://(.*?)/index\.php\?', urlBase).group(1)
	banner()
	usuario = read(msg='Usuario:')
	password = getpass.getpass("Contraseña:")
	if sesionActiva(usuario, urlBase):
		password2 = getpass.getpass('Confirme:')
		while password != password2:
			print('Las contraseñas no coinciden')
			password = getpass.getpass('Contraseña:')
			password2 = getpass.getpass('Confirme:')
	headers = {'Host': uni_url, 'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:54.0) Gecko/20100101 Firefox/54.0','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding':'gzip, deflate, br', 'Content-Type':'application/x-www-form-urlencoded', 'Referer': urlBase}
	payload = {'uni_url': uni_url, 'name': usuario, 'password': password, 'pwat_uid': '', 'pwat_checksum': '' ,'startPageShown' : '1' , 'detectedDevice' : '1' , 'kid':''}
	return Sesion(urlBase, payload, headers)

def main():
	checkFile()
	s = getSesion()
	setSignalsHandlers(s)
	try:
		menu(s)
	finally:
		s.updateCookieFile(salida=True)

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		pass
