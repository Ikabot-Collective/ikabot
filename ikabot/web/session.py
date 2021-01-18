#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import json
import time
import random
import getpass
import datetime
import gettext
import requests
import base64
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import banner
from ikabot.helpers.aesCipher import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCity

t = gettext.translation('session',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext


class Session:
	def __init__(self):
		self.logfile = '/tmp/ikabot.log'
		self.log = False
		self.padre = True
		self.logged = False
		self.__login()

	def __log(self, msg):
		if self.log is False:
			return
		now = datetime.datetime.now()
		entry = '{}:{}:{}\t{:d}: {}\n'.format(now.hour, now.minute, now.second, os.getpid(), msg)
		fh = open(self.logfile, 'a')
		fh.write(entry)
		fh.close()

	def __genRand(self):
		return hex(random.randint(0, 65535))[2:]

	def __genCookie(self):
		return self.__genRand() + self.__genRand() + hex(int(round(time.time() * 1000)))[2:] + self.__genRand() + self.__genRand()

	def __fp_eval_id(self):
		return self.__genRand() + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + self.__genRand() + self.__genRand()

	def __logout(self, html):
		if html is not None:
			idCiudad = getCity(html)['id']
			token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
			urlLogout = 'action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}'.format(idCiudad, token)
			self.s.get(self.urlBase + urlLogout)

	def __isInVacation(self, html):
		return 'nologin_umod' in html

	def __isExpired(self, html):
		return 'index.php?logout' in html
	
	def isExpired(self,html):
		return self.__isExpired(html)

	def __saveNewCookies(self):
		sessionData = self.getSessionData()

		cookie_dict = dict(self.s.cookies.items())
		sessionData['cookies'] = cookie_dict

		self.setSessionData(sessionData)

	def __getCookie(self, sessionData=None):
		if sessionData is None:
			sessionData = self.getSessionData()
		try:
			cookie_dict = sessionData['cookies']
			self.s = requests.Session()
			self.__update_proxy(sessionData=sessionData)
			self.s.headers.clear()
			self.s.headers.update(self.headers)
			requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
		except KeyError:
			self.__login(3)

	def __login(self, retries=0):
		self.__log('__login()')
		if not self.logged:
			banner()

			self.mail = read(msg=_('Mail:'))
			self.password = getpass.getpass(_('Password:'))

			banner()

		self.s = requests.Session()

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
		try:
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
		except Exception:
			pass # These cookies are not required and sometimes cause issues for people logging in

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


		self.host = 's{}-{}.ikariam.gameforge.com'.format(self.mundo, self.servidor)
		self.urlBase = 'https://{}/index.php?'.format(self.host)

		self.headers = {'Host': self.host, 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate, br', 'Referer': 'https://{}'.format(self.host), 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://{}'.format(self.host), 'DNT': '1', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}

		self.cipher = AESCipher(self.mail, self.username, self.password)
		sessionData = self.getSessionData()

		used_old_cookies = False
		# if there are cookies stored, try to use them
		if 'cookies' in sessionData and self.logged is False:
			# create a new temporary session object
			old_s = requests.Session()
			# set the headers
			old_s.headers.clear()
			old_s.headers.update(self.headers)
			# set the cookies to test
			cookie_dict = sessionData['cookies']
			requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=old_s.cookies, overwrite=True)
			self.__update_proxy(obj=old_s, sessionData=sessionData)
			try:
				# make a request to check the connection
				html = old_s.get(self.urlBase).text
			except:
				self.__proxy_error()

			cookies_are_valid = self.__isExpired(html) is False
			if cookies_are_valid:
				self.__log('using old cookies')
				used_old_cookies = True
				# assign the old cookies to the session object
				requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
				# set the proxy
				self.__update_proxy(sessionData=sessionData)
				# set the headers
				self.s.headers.clear()
				self.s.headers.update(self.headers)

		# login as normal and get new cookies
		if used_old_cookies is False:
			self.__log('using new cookies')
			resp = self.s.get('https://lobby.ikariam.gameforge.com/api/users/me/loginLink?id={}&server[language]={}&server[number]={}'.format(self.account['id'], self.servidor, self.mundo)).text
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

			# set the headers
			self.s.headers.clear()
			self.s.headers.update(self.headers)

			# set the proxy
			self.__update_proxy(sessionData=sessionData)

			# use the new cookies instead, invalidate the old ones
			try:
				html = self.s.get(url).text
			except:
				self.__proxy_error()

		if self.__isInVacation(html):
			msg = _('The account went into vacation mode')
			if self.padre:
				print(msg)
			else:
				sendToBot(self, msg)
			os._exit(0)
		if self.__isExpired(html):
			if retries > 0:
				return self.__login(retries-1)
			if self.padre:
				msg = _('Login error.')
				print(msg)
				os._exit(0)
			raise Exception('Couldn\'t log in')

		if not used_old_cookies:
			self.__saveNewCookies()

		self.logged = True

	def __backoff(self):
		self.__log('__backoff()')
		if self.padre is False:
			time.sleep(5 * random.randint(0, 10))

	def __sessionExpired(self):
		self.__log('__sessionExpired()')
		self.__backoff()

		sessionData = self.getSessionData()

		try:
			if self.s.cookies['PHPSESSID'] != sessionData['cookies']['PHPSESSID']:
				self.__getCookie(sessionData)
			else:
				try:
					self.__login(3)
				except Exception:
					self.__sessionExpired()
		except KeyError:
			try:
				self.__login(3)
			except Exception:
				self.__sessionExpired()

	def __proxy_error(self):
		sessionData = self.getSessionData()
		if 'proxy' not in sessionData or sessionData['proxy']['set'] is False:
			exit('network error')
		if self.padre is True:
			print(_('There seems to be a problem connecting to ikariam.'))
			print(_('Do you want to disable the proxy? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				exit()
			else:
				sessionData['proxy'] = {}
				sessionData['proxy']['conf'] = {}
				sessionData['proxy']['set']  = False
				self.setSessionData(sessionData)
				print(_('Proxy disabled, try again.'))
				enter()
				exit()
		else:
			msg = _('Network error. Consider disabling the proxy.')
			sendToBot(self, msg)
			exit()

	def __update_proxy(self, *, obj=None, sessionData=None):
		# set the proxy
		if obj is None:
			obj = self.s
		if sessionData is None:
			sessionData = self.getSessionData()
		if 'proxy' in sessionData:
			obj.proxies = sessionData['proxy']['conf']

	def __checkCookie(self):
		self.__log('__checkCookie()')
		sessionData = self.getSessionData()

		try:
			if self.s.cookies['PHPSESSID'] != sessionData['cookies']['PHPSESSID']:
				self.__getCookie(sessionData)
		except KeyError:
			try:
				self.__login(3)
			except Exception:
				self.__sessionExpired()

	def __token(self):
		"""Generates a valid actionRequest token from the session
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
		self.__update_proxy()

		if noIndex:
			url = self.urlBase.replace('index.php', '') + url
		else:
			url = self.urlBase + url
		self.__log('get({}), params:{}'.format(url, str(params)))
		while True:
			try:
				html = self.s.get(url, params=params).text #this isn't recursion, this get is different from the one it's in
				if ignoreExpire is False:
					assert self.__isExpired(html) is False
				return html
			except AssertionError:
				self.__sessionExpired()
			except requests.exceptions.ConnectionError:
				time.sleep(ConnectionError_wait)

	def post(self, url='', payloadPost={}, params={}, ignoreExpire=False, noIndex=False):
		"""Sends post request to ikariam
		Parameters
		----------
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
		url_original = url
		payloadPost_original = payloadPost
		params_original = params
		self.__checkCookie()
		self.__update_proxy()

		# add the request id
		token = self.__token()
		url = url.replace(actionRequest, token)
		if 'actionRequest' in payloadPost:
			payloadPost['actionRequest'] = token
		if 'actionRequest' in params:
			params['actionRequest'] = token

		if noIndex:
			url = self.urlBase.replace('index.php', '') + url
		else:
			url = self.urlBase + url
		self.__log('post({}), data={}'.format(url, str(payloadPost)))
		while True:
			try:
				resp = self.s.post(url, data=payloadPost, params=params).text
				if ignoreExpire is False:
					assert self.__isExpired(resp) is False
				if 'TXT_ERROR_WRONG_REQUEST_ID' in resp:
					self.__log(_('got TXT_ERROR_WRONG_REQUEST_ID'))
					return self.post(url=url_original, payloadPost=payloadPost_original, params=params_original, ignoreExpire=ignoreExpire, noIndex=noIndex)
				self.__log(resp)
				return resp
			except AssertionError:
				self.__sessionExpired()
			except requests.exceptions.ConnectionError:
				time.sleep(ConnectionError_wait)

	def logout(self):
		"""This function kills the current (chlid) process
		"""
		self.__log('logout({})')
		if self.padre is False:
			os._exit(0)

	def setSessionData(self, sessionData):
		"""Encrypts relevant session data and writes it to the .ikabot file
		Parameters
		----------
		sessionData : dict
			dictionary containing relevant session data, data is written to file using AESCipher.setSessionData
		"""
		self.cipher.setSessionData(self, sessionData)

	def getSessionData(self):
		"""Gets relevant session data from the .ikabot file
		"""
		return self.cipher.getSessionData(self)

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
