#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
try:
	import requests
except ImportError:
	sys.exit('Debe instalar el modulo de requests:\nsudo pip install requests')
import os
import time
import re
import random
import hashlib
import parser
from getJson import *
from sisop.varios import *
from pedirInfo import read

class Sesion:
	def __init__(self, urlBase, payload, headers):
		self.padre = True
		self.urlBase = urlBase
		self.payload = payload
		self.username = payload['name']
		self.password = payload['password']
		data = re.search(r'https://(s\d+)-(\w+)', urlBase)
		self.mundo = data.group(1)
		self.servidor = data.group(2)
		self.headers = headers
		self.sha = self.__hashPasswd()
		if self.__passwordEsValida():
			self.__getCookie()
		else:
			sys.exit('Usuario o contrasenia incorrecta')

	def __hashPasswd(self):
		sha = hashlib.sha256()
		sha.update(self.servidor.encode('utf-8') + b'0')
		sha.update(self.mundo.encode('utf-8') + b'0')
		sha.update(self.username.encode('utf-8') + b'0')
		sha.update(self.password.encode('utf-8'))
		return sha.hexdigest()

	def __passwordEsValida(self):
		sha = self.__getFileInfo()[0]
		if sha:
			sha = sha.group(4)
			return sha == self.__hashPasswd()
		else:
			return True # es el primero

	def __logout(self, html):
		if html is not None:
			idCiudad = getCiudad(html)['id']
			token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
			urlLogout = 'action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}'.format(idCiudad, token)
			self.s.get(self.urlBase + urlLogout, headers=self.headers)

	def __isMyCookie(self, line):
		string = self.servidor + ' ' + self.mundo + ' ' + self.username + ' '
		return string in line

	def __isExpired(self, html):
		return 'index.php?logout' in html

	def __updateCookieFile(self, primero=False, nuevo=False, salida=False):
		(fileInfo, text) = self.__getFileInfo()
		lines = text.splitlines()
		if primero is True:
			cookie_dict = dict(self.s.cookies.items())
			entrada = self.servidor + ' ' + self.mundo + ' ' + self.username + ' 1 ' + cookie_dict['PHPSESSID'] + ' ' + cookie_dict['ikariam'] + ' ' + self.sha
			newTextFile = ''
			for line in lines:
				if self.__isMyCookie(line) is False:
					newTextFile += line + '\n'
			newTextFile += entrada + '\n'
		else:
			if fileInfo is None:
				if nuevo is True:
					self.__updateCookieFile(primero=True)
				return

			oldline = fileInfo.group(0)
			sesionesActivas = int(fileInfo.group(1))
			newTextFile = ''

			if salida is True and sesionesActivas == 1:
				html = self.s.get(self.urlBase, headers=self.headers).text
				if self.__isExpired(html):
					html = None

			for line in lines:
				if line != oldline:
					newTextFile += line + '\n'
				else:
					if salida is True:
						if sesionesActivas > 1:
							newline = self.servidor + ' ' + self.mundo + ' ' + self.username + ' ' + str(sesionesActivas - 1) + ' ' + fileInfo.group(2) + ' ' + fileInfo.group(3) + ' ' + self.sha
							newTextFile += newline + '\n'
						else:
							self.__logout(html)
					elif nuevo is True:
						newline = self.servidor + ' ' + self.mundo + ' ' + self.username + ' ' + str(sesionesActivas + 1) + ' ' + fileInfo.group(2) + ' ' + fileInfo.group(3) + ' ' + self.sha
						newTextFile += newline + '\n'
		with open(cookieFile, 'w') as filehandler:
			filehandler.write(newTextFile)

	def __getCookie(self):
		fileInfo = self.__getFileInfo()[0]
		if fileInfo:
			cookie_dict = {'PHPSESSID': fileInfo.group(2), 'ikariam': fileInfo.group(3), 'ikariam_loginMode': '0'}
			self.s = requests.Session()
			requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
			self.__updateCookieFile(nuevo=True)
		else:
			self.__login()

	def __login(self):
		self.s = requests.Session() # s es la sesion de conexion
		html = self.s.post(self.urlBase + 'action=loginAvatar&function=login', data=self.payload, headers=self.headers).text
		if self.__isExpired(html):
			sys.exit('Usuario o contrasenia incorrecta')
		self.__updateCookieFile(primero=True)

	def __backoff(self):
		if self.padre is False:
			time.sleep(5 * random.randint(0, 10))

	def __expiroLaSesion(self):
		self.__backoff()
		if self.__sesionActiva():
			try:
				self.__login()
			except SystemExit:
				self.__expiroLaSesion()
		else:
			self.__getCookie()

	def __checkCookie(self):
		if self.__sesionActiva() is False:
			self.__getCookie()

	def __getFileInfo(self): # 1 num de sesiones 2 cookie1 3 cookie2 4 sha
		with open(cookieFile, 'r') as filehandler:
			text = filehandler.read()
		regex = re.escape(self.servidor) + r' ' + re.escape(self.mundo) + r' ' + re.escape(self.username) + r' (\d+) ([\w\d]+) ([\w\d_]+) ([\w\d]+)'
		return (re.search(regex, text), text)

	def __sesionActiva(self):
		fileInfo = self.__getFileInfo()[0]
		if fileInfo is None:
			return False
		else:
			try:
				return fileInfo.group(2) == self.s.cookies['PHPSESSID']
			except KeyError:
				return False

	def token(self):
		html = self.get()
		return re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)

	def get(self, url=None):
		self.__checkCookie()
		if url is None:
			url = ''
		url = self.urlBase + url
		while True:
			try:
				html = self.s.get(url, headers=self.headers).text
				assert self.__isExpired(html) is False
				return html
			except AssertionError:
				self.__expiroLaSesion()
			except requests.exceptions.ConnectionError:
				time.sleep(5 * 60)

	def post(self, url=None, payloadPost=None):
		self.__checkCookie()
		if url is None:
			url = ''
		url = self.urlBase + url
		payloadPost = payloadPost or {}
		while True:
			try:
				html = self.s.post(url, data=payloadPost, headers=self.headers).text
				assert self.__isExpired(html) is False
				return html
			except AssertionError:
				self.__expiroLaSesion()
			except requests.exceptions.ConnectionError:
				time.sleep(5 * 60)

	def login(self):
		self.__updateCookieFile(nuevo=True)

	def logout(self):
		self.__updateCookieFile(salida=True)
		if self.padre is False:
			os._exit(0)

def get(url):
	return requests.get(url)

def getSesion():
	global infoUser
	banner()
	html = get('https://es.ikariam.gameforge.com/?').text
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
		html = get('https://{}.ikariam.gameforge.com/?'.format(srv)).text
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
	return Sesion(urlBase, payload, headers)
