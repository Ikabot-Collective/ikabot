#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import json
import random
import gettext
import ikabot.config as config
import ikabot.web.sesion
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import *
from ikabot.config import *

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
	fileData = s.getFileData()
	try:
		ikabot.web.sesion.normal_get('https://api.telegram.org/bot{}/sendMessage'.format(fileData['telegram']['botToken']), params={'chat_id': fileData['telegram']['chatId'], 'text': msg})
	except KeyError:
		pass

def telegramCredsValidas(s):
	fileData = s.getFileData()
	try:
		return len(fileData['telegram']['botToken']) > 0 and len(fileData['telegram']['chatId']) > 0
	except KeyError:
		return False

def getUserResponse(s):
	fileData = s.getFileData()
	try:
		updates = ikabot.web.sesion.normal_get('https://api.telegram.org/bot{}/getUpdates'.format(fileData['telegram']['botToken'])).text
		updates = json.loads(updates, strict=False)
		if updates['ok'] is False:
			return []
		updates = updates['result']
		return [update['message']['text'] for update in updates if update['message']['chat']['id'] == int(fileData['telegram']['chatId'])]
	except KeyError:
		return []

def botValido(s):
	if telegramCredsValidas(s):
		return True
	else:
		banner()
		print(_('Debe proporcionar las credenciales válidas para comunicarse por telegram.'))
		print(_('Se requiere del token del bot a utilizar y de su chat_id'))
		print(_('Para más informacion sobre como obtenerlos vea al readme de https://github.com/physics-sp/ikabot'))
		rta = read(msg=_('¿Porporcionará las credenciales ahora? [y/N]'), values=['y','Y','n', 'N', ''])
		if rta.lower() != 'y':
			return False
		else:
			botToken = read(msg=_('Token del bot:'))
			chat_id = read(msg=_('Chat_id:'))

			fileData = s.getFileData()
			fileData['telegram'] = {}
			fileData['telegram']['botToken'] = botToken.replace(' ', '')
			fileData['telegram']['chatId'] = chat_id
			s.setFileData(fileData)

			rand = random.randint(1000, 9999)
			msg = _('El token a ingresar es:{:d}').format(rand)
			sendToBot(s, msg, Token=True)
			rta = read(msg=_('Se envio un mensaje por telegram, ¿lo recibió? [Y/n]'), values=['y','Y','n', 'N', ''])
			if rta.lower() == 'n':
				fileData['telegram']['botToken'] = ''
				fileData['telegram']['chatId'] = ''
				s.setFileData(fileData)
				print(_('Revíse las credenciales y vuelva a proveerlas.'))
				enter()
				return False
			else:
				recibido = read(msg=_('Ingrese el token recibido mediante telegram:'), digit=True)
				if rand != recibido:
					print(_('El token es incorrecto'))
					enter()
					return False
				else:
					print(_('El token es correcto.'))
					enter()
					return True
