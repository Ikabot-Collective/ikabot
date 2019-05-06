#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import ast
import sys
import json
import time
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
		self.cipher = AESCipher(payload)
		data = re.search(r'https://(s\d+)-(\w+)', urlBase)
		self.mundo = data.group(1)
		self.servidor = data.group(2)
		self.headers = headers
		self.alexaCook = self.__genCookie()
		self.gameforgeCook = self.__getGameforgeCookie()
		self.__getCookie()

	def __genRand(self):
		return hex(random.randint(0, 65535))[2:]

	def __genCookie(self):
		return self.__genRand() + self.__genRand() + hex(int(round(time.time() * 1000)))[2:] + self.__genRand() + self.__genRand()

	def __getGameforgeCookie(self):
		headers = {'Host': 'pixelzirkus.gameforge.com', 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:66.0) Gecko/20100101 Firefox/66.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded', 'DNT': '1', 'Connection': 'close', 'Upgrade-Insecure-Requests': '1'}
		cookies = {'__asc': self.alexaCook, '__auc': self.alexaCook}
		fp_eval_id = self.__genRand() + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + self.__genRand() + self.__genRand()
		page = self.urlBase.replace(self.mundo + '-', '').replace('index.php?', '')
		data = {'location': 'VISIT', 'product': 'ikariam', 'language': self.servidor, 'server-id': '1', 'replacement_kid': '', 'fp_eval_id': fp_eval_id, 'page': page,'referrer': '', 'fingerprint': '1820081159', 'fp_exec_time': '3.00'}
		r = requests.post('https://pixelzirkus.gameforge.com/do/simple', headers=headers, cookies=cookies, data=data)
		return r.cookies['pc_idt']

	def __logout(self, html):
		if html is not None:
			idCiudad = getCiudad(html)['id']
			token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
			urlLogout = 'action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}'.format(idCiudad, token)
			self.s.get(self.urlBase + urlLogout)

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
			plaintext = json.dumps(cookie_dict)
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
				html = self.s.get(self.urlBase).text
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
			cookie_dict = ast.literal_eval(plaintext)
			self.s = requests.Session()
			self.s.headers.clear()
			self.s.headers.update(self.headers)
			requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
			self.__updateCookieFile(nuevo=True)
		else:
			msg = _('La sesión se venció, renovando sesión')
			sendToBotDebug(msg, debugON_session)
			self.__login()

	def __login(self):
		self.s = requests.Session() # s es la sesion de conexion
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		self.s.cookies.update({'__asc': self.alexaCook, '__auc': self.alexaCook, 'pc_idt': self.gameforgeCook})
		html = self.s.post(self.urlBase + 'action=loginAvatar&function=login', data=self.payload).text
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
				cookie_dict = ast.literal_eval(plaintext)
				return cookie_dict['PHPSESSID'] == self.s.cookies['PHPSESSID']
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
				html = self.s.get(url).text
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
				html = self.s.post(url, data=payloadPost).text
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
