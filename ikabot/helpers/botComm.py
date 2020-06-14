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
	"""This function will send the ``msg`` argument passed to it as a message to the user on Telegram, only if ``debugOn`` is ``True``
	Parameters
	----------
	s : Session
		Session object 
	msg : str
		a string representing the message to send to the user on Telegram
	debugON : bool
		a boolean indicating whether or not to send the message.
	"""
	if debugON:
		sendToBot(s, msg)

def sendToBot(s, msg, Token=False):
	"""This function will send the ``msg`` argument passed to it as a message to the user on Telegram
	Parameters
	----------
	s : Session
		Session object
	msg : str
		a string representing the message to send to the user on Telegram
	Token : bool
		a boolean indicating whether or not to attach the process id, the users server, world and Ikariam username to the message
	"""
	if Token is False:
		msg = 'pid:{}\n{}\n{}'.format(os.getpid(), config.infoUser, msg)
	sessionData = s.getSessionData()
	try:
		ikabot.web.sesion.normal_get('https://api.telegram.org/bot{}/sendMessage'.format(sessionData['telegram']['botToken']), params={'chat_id': sessionData['telegram']['chatId'], 'text': msg})
	except KeyError:
		pass

def telegramDataIsValid(s):
	"""This function checks whether or not there is any Telegram data stored in the .ikabot file
	Parameters
	----------
	s : Session
		Session object
	
	Returns
	-------
	valid : bool
		a boolean indicating whether or not there is any Telegram data stored in the .ikabot file

	"""
	sessionData = s.getSessionData()
	try:
		return len(sessionData['telegram']['botToken']) > 0 and len(sessionData['telegram']['chatId']) > 0
	except KeyError:
		return False

def getUserResponse(s):
	"""This function will retrieve a list of messages the user sent to the bot on Telegram.
	Parameters
	----------
	s : Session
		Session object

	Returns
	-------
	updates : list[str]
		a list containing all the messages the user sent to the bot on Telegram
	"""
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
	"""This function doesn't actually check any data itself, that is done by the ``telegramDataIsValid`` function. This function returns ``True`` if there is any Telegram data in the .ikabot file, and if there is none, it will ask the user to input it.
	Parameters
	----------
	s : Session
		Session object

	Returns
	-------
	valid : bool
		a boolean indicating whether or not there is valid Telegram data in the .ikabot file.
	"""
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
	"""This function asks the user to input the Telegram bot's token and the user's own Telegram chat id. After the user has inputted the neccessary data, this function will generate a random 4 digit number, send it to the user as a Telegram message using the token the user provided. It will then ask the user to input that number as validation.
	Parameters
	----------
	s : Session
		Session object
	e : multiprocessing.Event
		an event which, when fired, give back control of the terminal to the main process
	fd : int
		the standard input file descriptor passed to the function as a means of gaining control of the terminal
	
	Returns
	-------
	valid : bool
		a boolean indicating whether or not the Telegram data has been successfully updated
	"""
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
