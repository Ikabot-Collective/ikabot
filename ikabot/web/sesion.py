#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import re
import random
import parser
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.botComm import *
from ikabot.helpers.aesCipher import *
from ikabot.config import *
import gettext

t = gettext.translation('sesion', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

try:
	import requests
except ImportError:
	sys.exit(_('Debe instalar el modulo de requests:\nsudo pip3 install requests'))

class Sesion:
	def __init__(self, urlBase, payload, headers):
		self.padre = True
		self.urlBase = urlBase
		self.payload = payload
		self.username = payload['name']
		self.cipher = AESCipher(payload['password'])
		data = re.search(r'https://(s\d+)-(\w+)', urlBase)
		self.mundo = data.group(1)
		self.servidor = data.group(2)
		self.headers = headers
		self.__getCookie()

	def __logout(self, html):
		if html is not None:
			idCiudad = getCiudad(html)['id']
			token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
			urlLogout = 'action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}'.format(idCiudad, token)
			self.s.get(self.urlBase + urlLogout, headers=self.headers)

	def __isMyCookie(self, line):
		string = self.servidor + ' ' + self.mundo + ' ' + self.username + ' '
		return string in line

	def __isInVacation(self, html):
		return 'nologin_umod' in html

	def __isExpired(self, html):
		return 'index.php?logout' in html

	def __updateCookieFile(self, primero=False, nuevo=False, salida=False):
		msg = _('Actualizo el archivo de cookies:\n')
		if primero:
			msg += _('Primero')
		elif nuevo:
			msg += _('Nuevo')
		else:
			msg += _('Salida')
		sendToBotDebug(msg, debugON_session)

		(fileInfo, text) = self.__getFileInfo()
		lines = text.splitlines()
		if primero is True:
			cookie_dict = dict(self.s.cookies.items())
			plaintext = cookie_dict['PHPSESSID'] + ' ' + cookie_dict['ikariam']
			ciphertext = self.cipher.encrypt(plaintext)
			entrada = self.servidor + ' ' + self.mundo + ' ' + self.username + ' 1 ' + ciphertext
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
							newline = self.servidor + ' ' + self.mundo + ' ' + self.username + ' ' + str(sesionesActivas - 1) + ' ' + fileInfo.group(2)
							newTextFile += newline + '\n'
						else:
							self.__logout(html)
					elif nuevo is True:
						newline = self.servidor + ' ' + self.mundo + ' ' + self.username + ' ' + str(sesionesActivas + 1) + ' ' + fileInfo.group(2)
						newTextFile += newline + '\n'
		with open(cookieFile, 'w', os.O_NONBLOCK) as filehandler:
			filehandler.write(newTextFile)
			filehandler.flush()

	def __getCookie(self):
		fileInfo = self.__getFileInfo()[0]
		if fileInfo:
			msg = _('actualizo cookie usando el archivo de cookies')
			sendToBotDebug(msg, debugON_session)
			ciphertext = fileInfo.group(2)
			try:
				plaintext = self.cipher.decrypt(ciphertext)
			except ValueError:
				if self.padre:
					print(_('Usuario o contrasenia incorrecta'))
				else:
					sendToBot(_('MAC check ERROR, ciphertext corrompido.'))
				os._exit(0)
			cookie1, cookie2 = plaintext.split(' ')
			cookie_dict = {'PHPSESSID': cookie1, 'ikariam': cookie2, 'ikariam_loginMode': '0'}
			self.s = requests.Session()
			requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
			self.__updateCookieFile(nuevo=True)
		else:
			msg = _('La sesión se venció, renovando sesión')
			sendToBotDebug(msg, debugON_session)
			self.__login()

	def __login(self):
		self.s = requests.Session() # s es la sesion de conexion
		html = self.s.post(self.urlBase + 'action=loginAvatar&function=login', data=self.payload, headers=self.headers).text
		if self.__isInVacation(html):
			msg = 'La cuenta entró en modo vacaciones'
			if self.padre:
				print(msg)
			else:
				sendToBot(msg)
			os._exit(0)
		if self.__isExpired(html):
			if self.padre:
				msg = _('Usuario o contrasenia incorrecta')
				print(msg)
				os._exit(0)
			raise Exception('No se pudo iniciar sesión')
		self.__updateCookieFile(primero=True)

	def __backoff(self):
		if self.padre is False:
			time.sleep(5 * random.randint(0, 10))

	def __expiroLaSesion(self):
		self.__backoff()
		if self.__sesionActiva():
			try:
				self.__login()
			except Exception:
				self.__expiroLaSesion()
		else:
			try:
				self.__getCookie()
			except Exception:
				self.__expiroLaSesion()

	def __checkCookie(self):
		if self.__sesionActiva() is False:
			try:
				self.__getCookie()
			except Exception:
				self.__expiroLaSesion()

	def __getFileInfo(self): # 1 num de sesiones 2 ciphertext
		with open(cookieFile, 'r', os.O_NONBLOCK) as filehandler:
			text = filehandler.read()
		regex = re.escape(self.servidor) + r' ' + re.escape(self.mundo) + r' ' + re.escape(self.username) + r' (\d+) (.+)'
		return (re.search(regex, text), text)

	def __sesionActiva(self):
		fileInfo = self.__getFileInfo()[0]
		if fileInfo:
			ciphertext = fileInfo.group(2)
			try:
				plaintext = self.cipher.decrypt(ciphertext)
				cookie = plaintext.split(' ')[0]
				return cookie == self.s.cookies['PHPSESSID']
			except ValueError:
				msg = 'MAC check ERROR, ciphertext corrompido.'
				if self.padre:
					print(msg)
				else:
					sendToBot(msg)
				os._exit(0)
			except KeyError:
				pass
		return False

	def token(self):
		html = self.get()
		return re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)

	def get(self, url=''):
		self.__checkCookie()
		url = self.urlBase + url
		while True:
			try:
				html = self.s.get(url, headers=self.headers).text
				assert self.__isExpired(html) is False
				return html
			except AssertionError:
				self.__expiroLaSesion()
			except requests.exceptions.ConnectionError:
				time.sleep(ConnectionError_wait)

	def post(self, url='', payloadPost={}):
		self.__checkCookie()
		url = self.urlBase + url
		while True:
			try:
				html = self.s.post(url, data=payloadPost, headers=self.headers).text
				assert self.__isExpired(html) is False
				return html
			except AssertionError:
				self.__expiroLaSesion()
			except requests.exceptions.ConnectionError:
				time.sleep(ConnectionError_wait)

	def login(self):
		self.__updateCookieFile(nuevo=True)

	def logout(self):
		self.__updateCookieFile(salida=True)
		if self.padre is False:
			os._exit(0)

def normal_get(url, params={}):
	try:
		return requests.get(url, params=params)
	except requests.exceptions.ConnectionError:
		sys.exit(_('Fallo la conexion a internet'))
