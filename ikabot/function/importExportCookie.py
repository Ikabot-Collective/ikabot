#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import gettext
import json
import sys
import requests
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import *
from ikabot.config import *

t = gettext.translation('insertCookies',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def importExportCookie(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	banner()
	try:
		print('Do you want to import or export the cookie?')
		print('(0) Exit')
		print('(1) Import')
		print('(2) Export')
		action = read(min=0, max=2)
		if action == 1:
			importCookie(session)
		elif action == 2:
			exportCookie(session)
		
		event.set()
	except KeyboardInterrupt:
		event.set()
		return

def importCookie(session):
	banner()
	print('{}⚠️ INSERTING AN INVALID COOKIE WILL LOG YOU OUT OF YOUR OTHER SESSIONS ⚠️{}\n\n'.format(bcolors.WARNING, bcolors.ENDC))
	print('Go ahead and export the cookie from another ikabot instance now and then')
	print('type your "ikariam" cookie below:')
	newcookie = read()
	newcookie = newcookie.strip()
	newcookie = newcookie.replace('ikariam=','')
	cookies = session.getSessionData()['cookies']
	cookies['ikariam'] = newcookie
	if session.host in session.s.cookies._cookies:
		session.s.cookies.set('ikariam', newcookie, domain = session.host, path = '/')
	else:
		session.s.cookies.set('ikariam', newcookie, domain = '', path = '/')

	html = session.s.get(session.urlBase).text

	if session.isExpired(html):
		print('{}Failure!{} All your other sessions have just been invalidated!'.format(bcolors.RED, bcolors.ENDC))
		enter()
	else:
		print('{}Success!{} This ikabot session will now use the cookie you provided'.format(bcolors.GREEN, bcolors.ENDC))
		sessionData = session.getSessionData()
		sessionData['cookies']['ikariam'] = newcookie
		session.setSessionData(sessionData)
		enter()
	session.get()

def exportCookie(session):
	banner()
	session.get() #get valid cookie in case user has logged the bot out before running this feature
	ikariam = session.getSessionData()['cookies']['ikariam']
	print('Use this cookie to synchronise two ikabot instances on 2 different machines\n\n')
	print('ikariam='+ikariam+'\n\n')

	cookie = json.dumps({"ikariam" : ikariam}) #get ikariam cookie, only this cookie is invalidated when the bot logs the user out.
	cookies_js = 'cookies={};i=0;for(let cookie in cookies){{document.cookie=Object.keys(cookies)[i]+\"=\"+cookies[cookie];i++}}'.format(cookie)
	print("""To prevent ikabot from logging you out while playing Ikariam do the following:
	1. Be on the "Your session has expired" screen
	2. Open Chrome javascript console by pressing CTRL + SHIFT + J
	3. Copy the text below, paste it into the console and press enter
	4. Press F5
	""")
	print(cookies_js)
	enter()
	