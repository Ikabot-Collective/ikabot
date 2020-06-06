#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import json
import time
import random
import getpass
import gettext
import requests
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import banner
from ikabot.helpers.aesCipher import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCiudad

t = gettext.translation('sesion', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext


class Sesion:
	def __init__(self):
		self.padre = True
		self.logged = False
		self.__login()

	def __genRand(self):
		return hex(random.randint(0, 65535))[2:]

	def __genCookie(self):
		return self.__genRand() + self.__genRand() + hex(int(round(time.time() * 1000)))[2:] + self.__genRand() + self.__genRand()

	def __fp_eval_id(self):
		return self.__genRand() + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + self.__genRand() + self.__genRand()

	def __logout(self, html):
		if html is not None:
			idCiudad = getCiudad(html)['id']
			token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
			urlLogout = 'action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}'.format(idCiudad, token)
			self.s.get(self.urlBase + urlLogout)

	def __isInVacation(self, html):
		return 'nologin_umod' in html

	def __isExpired(self, html):
		return 'index.php?logout' in html

	def __updateCookieFile(self, primero=False, nuevo=False, salida=False):
		msg = _('Updating the cookie file:\n')
		if primero:
			msg += _('First')
		elif nuevo:
			msg += _('New')
		else:
			msg += _('Out')
#		sendToBotDebug(self, msg, debugON_session)

		fileData = self.getFileData()

		if primero is True:
			cookie_dict = dict(self.s.cookies.items())
			fileData['cookies'] = cookie_dict
			fileData['num_sesiones'] = 1

		elif nuevo is True:
			try:
				fileData['num_sesiones'] += 1
			except KeyError:
				fileData['num_sesiones'] = 1

		elif salida is True:
			try:
				if fileData['num_sesiones'] == 1:
					html = self.s.get(self.urlBase).text
					if self.__isExpired(html) is False:
						self.__logout(html)
			except KeyError:
				return
			fileData['num_sesiones'] -= 1

		self.setFileData(fileData)

	def __getCookie(self, fileData=None):
		if fileData is None:
			fileData = self.getFileData()
		try:
			assert fileData['num_sesiones'] > 0
			cookie_dict = fileData['cookies']
			self.s = requests.Session()
			self.s.proxies = proxyDict
			self.s.headers.clear()
			self.s.headers.update(self.headers)
			requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
			self.__updateCookieFile(nuevo=True)
		except (KeyError, AssertionError):
			msg = _('Updating cookie using cookie file')
			sendToBotDebug(self, msg, debugON_session)
			self.__login(3)

	def __login(self, retries=0):
		if not self.logged:
			banner()

			self.mail = read(msg=_('Mail:'))
			self.password = getpass.getpass(_('Password:'))

			banner()

		self.s = requests.Session()
		self.s.proxies = proxyDict

		# get gameEnvironmentId and platformGameId
		self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		r = self.s.get('https://lobby.ikariam.gameforge.com/config/configuration.js')

		js = r.text
		gameEnvironmentId = re.search(r'"gameEnvironmentId":"(.*?)"', js)
		if gameEnvironmentId is None:
			exit('gameEnvironmentId not found')
		gameEnvironmentId = gameEnvironmentId.group(1)
		platformGameId = re.search(r'"platformGameId":"(.*?)"', js)
		if platformGameId is None:
			exit('platformGameId not found')
		platformGameId = platformGameId.group(1)

		# get __cfduid cookie
		self.headers = {'Host': 'gameforge.com', 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		r = self.s.get('https://gameforge.com/js/connect.js')
		html = r.text
		captcha = re.search(r'Attention Required', html)
		if captcha is not None:
			exit('Captcha error!')

		# update __cfduid cookie
		self.headers = {'Host': 'gameforge.com', 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Origin': 'https://lobby.ikariam.gameforge.com', 'DNT': '1', 'Connection': 'close'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		r = self.s.get('https://gameforge.com/config')

		__fp_eval_id_1 = self.__fp_eval_id()
		__fp_eval_id_2 = self.__fp_eval_id()

		# get pc_idt cookie
		self.headers = {'Host': 'pixelzirkus.gameforge.com', 'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://lobby.ikariam.gameforge.com', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Upgrade-Insecure-Requests': '1'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		data = {'product': 'ikariam', 'server_id': '1', 'language': 'en', 'location': 'VISIT', 'replacement_kid': '', 'fp_eval_id': __fp_eval_id_1, 'page': 'https%3A%2F%2Flobby.ikariam.gameforge.com%2F', 'referrer': '', 'fingerprint': '2175408712', 'fp_exec_time': '1.00'}
		r = self.s.post('https://pixelzirkus.gameforge.com/do/simple', data=data)

		# update pc_idt cookie
		self.headers = {'Host': 'pixelzirkus.gameforge.com', 'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://lobby.ikariam.gameforge.com', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Upgrade-Insecure-Requests': '1'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		data = {'product': 'ikariam', 'server_id': '1', 'language': 'en', 'location': 'fp_eval', 'fp_eval_id': __fp_eval_id_2, 'fingerprint': '2175408712', 'fp2_config_id': '1', 'page': 'https%3A%2F%2Flobby.ikariam.gameforge.com%2F', 'referrer': '', 'fp2_value': '921af958be7cf2f76db1e448c8a5d89d', 'fp2_exec_time': '96.00'}
		r = self.s.post('https://pixelzirkus.gameforge.com/do/simple', data=data)

		# options req (not really needed)
		self.headers = {'Host': 'gameforge.com','User-Agent': user_agent,'Accept': '*/*','Accept-Language': 'en-US,en;q=0.5','Accept-Encoding': 'gzip, deflate','Access-Control-Request-Method': 'POST','Access-Control-Request-Headers': 'content-type,tnt-installation-id','Referer': 'https://lobby.ikariam.gameforge.com/es_AR/','Origin': 'https://lobby.ikariam.gameforge.com','DNT': '1','Connection': 'close'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		r = self.s.options('https://gameforge.com/api/v1/auth/thin/sessions')

		# send creds
		self.headers = {'Host': 'gameforge.com','User-Agent': user_agent,'Accept': '*/*','Accept-Language': 'en-US,en;q=0.5','Accept-Encoding': 'gzip, deflate, br','Referer': 'https://lobby.ikariam.gameforge.com/es_AR/','TNT-Installation-Id': '','Content-Type': 'application/json','Origin': 'https://lobby.ikariam.gameforge.com','DNT': '1','Connection': 'keep-alive','Pragma': 'no-cache','Cache-Control': 'no-cache','TE': 'Trailers'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		data = {"identity": self.mail, "password": self.password, "locale":"es_AR", "gfLang":"ar", "platformGameId": platformGameId, "gameEnvironmentId": gameEnvironmentId, "autoGameAccountCreation": "false"}
		r = self.s.post('https://gameforge.com/api/v1/auth/thin/sessions', json=data)
		if r.status_code == 403:
			exit(_('Wrong email or password\n'))

		# get the authentication token and set the cookie
		ses_json = json.loads(r.text, strict=False)
		auth_token = ses_json['token']
		cookie_obj = requests.cookies.create_cookie(domain='.gameforge.com', name='gf-token-production', value=auth_token)
		self.s.cookies.set_cookie(cookie_obj)

		# get accounts
		self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/es_AR/hub', 'Authorization': 'Bearer {}'.format(auth_token), 'DNT': '1', 'Connection': 'close'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		r = self.s.get('https://lobby.ikariam.gameforge.com/api/users/me/accounts')
		accounts = json.loads(r.text, strict=False)

		# get servers
		self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/es_AR/hub', 'Authorization': 'Bearer {}'.format(auth_token), 'DNT': '1', 'Connection': 'close'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		r = self.s.get('https://lobby.ikariam.gameforge.com/api/servers')
		servers = json.loads(r.text, strict=False)

		if not self.logged:

			if len([ account for account in accounts if account['blocked'] is False ]) == 1:
				self.account  = [ account for account in accounts if account['blocked'] is False ][0]
			else:
				print(_('With which account do you want to log in?\n'))

				max_name = max( [ len(account['name']) for account in accounts if account['blocked'] is False ] )
				i = 0
				for account in [ account for account in accounts if account['blocked'] is False ]:
					server = account['server']['language']
					mundo = account['server']['number']
					world = [ srv['name'] for srv in servers if srv['language'] == server and srv['number'] == mundo ][0]
					i += 1
					pad = ' ' * (max_name - len(account['name']))
					print('({:d}) {}{} [{} - {}]'.format(i, account['name'], pad, server, world))
				num = read(min=1, max=i)
				self.account  = [ account for account in accounts if account['blocked'] is False ][num - 1]
			self.username = self.account['name']
			self.servidor = self.account['server']['language']
			self.mundo    = str(self.account['server']['number'])
			self.word     = [ srv['name'] for srv in servers if srv['language'] == self.servidor and srv['number'] == int(self.mundo) ][0]
			config.infoUser = _('Server:{}').format(self.servidor)
			config.infoUser += _(', World:{}').format(self.word)
			config.infoUser += _(', Player:{}').format(self.username)
			banner()

		resp = self.s.get('https://lobby.ikariam.gameforge.com/api/users/me/loginLink?id={}&server[language]={}&server[number]={}'.format(self.account['id'], self.servidor, self.mundo)).text
		self.s.cookies.__delitem__('PHPSESSID')
		resp = json.loads(resp, strict=False)
		if 'url' not in resp:
			if retries > 0:
				return self.__login(retries-1)
			else:
				msg = 'Login Error: ' + str(resp)
				if self.padre:
					print(msg)
					exit()
				else:
					exit(msg)

		url = resp['url']
		match = re.search(r'https://s\d+-\w{2}\.ikariam\.gameforge\.com/index\.php\?', url)
		if match is None:
			exit('Error')

		self.urlBase = match.group(0)
		self.host = self.urlBase.split('//')[1].split('/index')[0]
		self.headers = {'Host': self.host, 'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/es_AR/accounts', 'Upgrade-Insecure-Requests': '1'}
		self.s.headers.clear()
		self.s.headers.update(self.headers)
		html = self.s.get(url).text

		if self.__isInVacation(html):
			msg = _('The account went into vacation mode')
			if self.padre:
				print(msg)
			else:
				sendToBot(self, msg)
			os._exit(0)
		if self.__isExpired(html):
			if self.padre:
				msg = _('Login error.')
				print(msg)
				os._exit(0)
			raise Exception('No se pudo iniciar sesión')
		self.cipher = AESCipher(self.mail, self.username, self.password)
		self.__updateCookieFile(primero=True)
		self.logged = True

	def __backoff(self):
		if self.padre is False:
			time.sleep(5 * random.randint(0, 10))

	def __expiroLaSesion(self):
		self.__backoff()

		fileData = self.getFileData()

		try:
			if fileData['num_sesiones'] > 0 and self.s.cookies['PHPSESSID'] != fileData['cookies']['PHPSESSID']:
				self.__getCookie(fileData)
			else:
				try:
					self.__login(3)
				except Exception:
					self.__expiroLaSesion()
		except KeyError:
			try:
				self.__login(3)
			except Exception:
				self.__expiroLaSesion()

	def __checkCookie(self):
		fileData = self.getFileData()

		try:
			if fileData['num_sesiones'] > 0:
				if self.s.cookies['PHPSESSID'] != fileData['cookies']['PHPSESSID']:
					self.__getCookie(fileData)
			else:
				try:
					self.__login(3)
				except Exception:
					self.__expiroLaSesion()
		except KeyError:
			try:
				self.__login(3)
			except Exception:
				self.__expiroLaSesion()

	def token(self):
		"""Generates a valid actionRequest token from the session
		Parameters
		----------
		self : Session
			Session object

		Returns
		-------
		token : str
			a string representing a valid actionRequest token
		"""
		html = self.get()
		return re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)

	def get(self, url='', params={}, ignoreExpire=False, noIndex=False):
		"""Sends get request to ikariam
		Parameters
		----------
		self : Sesion
			Session object
		url : str
			this string will be appended to the end of the urlBase of the Session object. urlBase will look like: 'https://s(number)-(country).ikariam.gameforge.com/index.php?'
		params : dict
			dictionary containing key-value pairs which represent the parameteres of the get request
		ignoreExpire: bool
			if set to True it will ignore if the current session is expired and will simply return whatever response it gets. If it's set to False, it will make sure that the current session is not expired before sending the get request, if it's expired it will login again
		noIndex : bool
			if set to True it will remove 'index.php' from the end of urlBase before appending url params and sending the get request
		
		Returns
		-------
		html : str
			response from the server
		"""
		self.__checkCookie()
		if noIndex:
			url = self.urlBase.replace('index.php', '') + url
		else:
			url = self.urlBase + url
		while True:
			try:
				html = self.s.get(url, params=params).text #this isn't recursion, this get is different from the one it's in
				if ignoreExpire is False:
					assert self.__isExpired(html) is False
				return html
			except AssertionError:
				self.__expiroLaSesion()
			except requests.exceptions.ConnectionError:
				time.sleep(ConnectionError_wait)

	def post(self, url='', payloadPost={}, params={}, ignoreExpire=False, noIndex=False):
		"""Sends post request to ikariam
		Parameters
		----------
		self : Sesion
			Session object
		url : str
			this string will be appended to the end of the urlBase of the Session object. urlBase will look like: 'https://s(number)-(country).ikariam.gameforge.com/index.php?'
		payloadPost : dict
			dictionary containing key-value pairs which represent the payload of the post request
		params : dict
			dictionary containing key-value pairs which represent the parameteres of the post request
		ignoreExpire: bool
			if set to True it will ignore if the current session is expired and will simply return whatever response it gets. If it's set to False, it will make sure that the current session is not expired before sending the post request, if it's expired it will login again
		noIndex : bool
			if set to True it will remove 'index.php' from the end of urlBase before appending url and params and sending the post request
		
		Returns
		-------
		html : str
			response from the server
		"""
		self.__checkCookie()
		if noIndex:
			url = self.urlBase.replace('index.php', '') + url
		else:
			url = self.urlBase + url
		while True:
			try:
				html = self.s.post(url, data=payloadPost, params=params).text
				if ignoreExpire is False:
					assert self.__isExpired(html) is False
				return html
			except AssertionError:
				self.__expiroLaSesion()
			except requests.exceptions.ConnectionError:
				time.sleep(ConnectionError_wait)

	def login(self):
		"""This function doesn't actually log into ikariam, it only increments a number in the .ikabot file which represents the number currently running sessions
		Parameters
		----------
		self: Session
			Session object
		"""
		self.__updateCookieFile(nuevo=True)

	def logout(self):
		"""This function decrements a number in the .ikabot file representing the number of currently running sessions. If this number is 1, it will attempt to completely log out of ikariam
		Parameters
		----------
		self: Session
			Session object
		"""
		self.__updateCookieFile(salida=True)
		if self.padre is False:
			os._exit(0)

	def setFileData(self, fileData):
		"""Encrypts relevant session data and writes it to the .ikabot file
		Parameters
		----------
		self : Session
			Session object
		fileData : dict
			dictionary containing relevant session data, data is written to file using AESCipher.setFileData
		"""
		self.cipher.setFileData(self, fileData)

	def getFileData(self):
		"""Gets relevant session data from the .ikabot file
		self : Session
			Session object
		"""
		return self.cipher.getFileData(self)

def normal_get(url, params={}):
	"""Sends a get request to provided url
	Parameters
	----------
	url : str
		a string representing the url to which to send the get request
	params : dict
		a dictionary containing key-value pairs which represent the parameters of the get request
	
	Returns
	-------
	response : requests.Response
		a requests.Response object which represents the webservers response. For more information on requests.Response refer to https://requests.readthedocs.io/en/master/api/#requests.Response
	"""
	try:
		return requests.get(url, params=params)
	except requests.exceptions.ConnectionError:
		sys.exit(_('Internet connection failed'))
