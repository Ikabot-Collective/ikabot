#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import gettext
import json
import sys
from ikabot.helpers.gui import *
from ikabot.config import *

t = gettext.translation('insertCookies',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def insertCookies(session, event, stdin_fd):
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
		cookies = json.dumps(session.getSessionData()['cookies'])
		cookies_js = 'cookies={};i=0;for(let cookie in cookies){{document.cookie=Object.keys(cookies)[i]+\"=\"+cookies[cookie];i++}}'.format(cookies)
		print("""To prevent ikabot from logging you out while playing Ikariam do the following:
		1. While you're in Ikariam on the "Your session has expired screen" open chrome developer tools by pressing CTRL + SHIFT + I
		2. Open the Application tab in developer tools (You may need to press CONTROL + SHIFT + D to be able to see it)
		3. Click Cookies
		4. Click on the tab named s[number]-[region].ikariam.gameforge.com 
		5. Delete all the cookies by clicking on them and pressing DEL on your keyboard
		6. Open the Console tab in developer tools
		7. Copy the text below, paste it into the console and press enter
		8. Press F5
		""")
		print(cookies_js)
		enter()
		event.set()
	except KeyboardInterrupt:
		event.set()
		return
