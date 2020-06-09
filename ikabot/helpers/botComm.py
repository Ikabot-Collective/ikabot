#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import json
import random
import gettext
import sys
import ikabot.web.sesion
from ikabot.config import *
import ikabot.config as config
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read

t = gettext.translation('botComm', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def sendToBotDebug(s ,msg, debugON):
	if debugON:
		sendToBot(s, msg)

def sendToBot(s, msg, Token=False):
	if Token is False:
		msg = 'pid:{}\n{}\n{}'.format(os.getpid(), config.infoUser, msg)
	sessionData = s.getSessionData()
	try:
		ikabot.web.sesion.normal_get('https://api.telegram.org/bot{}/sendMessage'.format(sessionData['telegram']['botToken']), params={'chat_id': sessionData['telegram']['chatId'], 'text': msg})
	except KeyError:
		pass

def telegramDataIsValid(s):
	sessionData = s.getSessionData()
	try:
		return len(sessionData['telegram']['botToken']) > 0 and len(sessionData['telegram']['chatId']) > 0
	except KeyError:
		return False

def getUserResponse(s):
	# returns messages that the user sends to the telegram bot
	sessionData = s.getSessionData()
	try:
		updates = ikabot.web.sesion.normal_get('https://api.telegram.org/bot{}/getUpdates'.format(sessionData['telegram']['botToken'])).text
		updates = json.loads(updates, strict=False)
		if updates['ok'] is False:
			return []
		updates = updates['result']
		# only return messages from the chatId of our user
		return [update['message']['text'] for update in updates if update['message']['chat']['id'] == int(sessionData['telegram']['chatId'])]
	except KeyError:
		return []

def checkTelegramData(s):
	if telegramDataIsValid(s):
		return True
	else:
		banner()
		print(_('You must provide valid credentials to communicate by telegram.'))
		print(_('You require the token of the bot you are going to use and your chat_id'))
		print(_('For more information about how to obtain them read the readme at https://github.com/physics-sp/ikabot'))
		rta = read(msg=_('Will you provide the credentials now? [y/N]'), values=['y','Y','n', 'N', ''])
		if rta.lower() != 'y':
			return False
		else:
			return updateTelegramData(s)

def updateTelegramData(s, e=None, fd=None):
	if e is not None and fd is not None:
		sys.stdin = os.fdopen(fd) # give process access to terminal

	banner()
	botToken = read(msg=_('Bot\'s token:'))
	chat_id = read(msg=_('Chat_id:'))

	sessionData = s.getSessionData()
	sessionData['telegram'] = {}
	sessionData['telegram']['botToken'] = botToken.replace(' ', '').replace('.', '')
	sessionData['telegram']['chatId'] = chat_id
	s.setSessionData(sessionData)

	rand = random.randint(1000, 9999)
	msg = _('El token a ingresar es:{:d}').format(rand)
	sendToBot(s, msg, Token=True)

	rta = read(msg=_('A message was sent by telegram, did you receive it? [Y/n]'), values=['y','Y','n', 'N', ''])
	if rta.lower() == 'n':
		valid = False
	else:
		recibido = read(msg=_('Enter the received token in telegram:'), digit=True)
		if rand != recibido:
			print(_('The token is incorrect'))
			valid = False
		else:
			print(_('The token is correct'))
			valid = True

	if valid is False:
		sessionData['telegram']['botToken'] = ''
		sessionData['telegram']['chatId'] = ''
		s.setSessionData(sessionData)
		print(_('Check the credentials and re-supply them.'))
	else:
		print(_('The data was saved.'))
	enter()

	if e is not None and fd is not None:
		e.set() #give main process control before exiting
	return valid
