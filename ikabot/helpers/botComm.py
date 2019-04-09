#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import random
import gettext
import ikabot.config as config
import ikabot.web.sesion
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import enter
from ikabot.config import *

t = gettext.translation('botComm', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def sendToBotDebug(msg, debugON):
	if debugON:
		sendToBot(msg)

def sendToBot(msg, Token=False):
	if Token is False:
		msg = 'pid:{}\n{}\n{}'.format(os.getpid(), config.infoUser, msg)
	with open(config.telegramFile, 'r', os.O_NONBLOCK) as filehandler:
		text = filehandler.read()
	valid = re.search(r'\d{6,}:[A-Za-z0-9_-]{34,}\n\d{8,9}', text)
	if valid is not None:
		(botToken, chatId) = text.splitlines()
		ikabot.web.sesion.normal_get('https://api.telegram.org/bot{}/sendMessage'.format(botToken), params={'chat_id': chatId, 'text': msg})

def telegramFileValido():
	with open(config.telegramFile, 'r', os.O_NONBLOCK) as filehandler:
		text = filehandler.read()
	valid = re.search(r'\d{6,}:[A-Za-z0-9_-]{34,}\n\d{8,9}', text)
	return valid is not None

def botValido(s):
	if telegramFileValido():
		return True
	else:
		print(_('Debe proporcionar las credenciales válidas para comunicarse por telegram.'))
		print(_('Se requiere del token del bot a utilizar y de su chat_id'))
		print(_('Para más informacion sobre como obtenerlos vea al readme de https://github.com/physics-sp/ikabot'))
		rta = read(msg=_('¿Porporcionará las credenciales ahora? [y/N]'), values=['y','Y','n', 'N', ''])
		if rta.lower() != 'y':
			return False
		else:
			botToken = read(msg=_('Token del bot:'))
			chat_id = read(msg=_('Chat_id:'))
			with open(config.telegramFile, 'w', os.O_NONBLOCK) as filehandler:
				filehandler.write(botToken + '\n' + chat_id)
				filehandler.flush()
			rand = random.randint(1000, 9999)
			msg = _('El token a ingresar es:{:d}').format(rand)
			sendToBot(msg, Token=True)
			rta = read(msg=_('Se envio un mensaje por telegram, ¿lo recibió? [Y/n]'), values=['y','Y','n', 'N', ''])
			if rta.lower() == 'n':
				with open(config.telegramFile, 'w', os.O_NONBLOCK) as file:
					pass
				print(_('Revíse las credenciales y vuelva a proveerlas.'))
				enter()
				return False
			else:
				recibido = read(msg=_('Ingrese el token recibido mediante telegram:'), digit=True)
				if rand != recibido:
					with open(config.telegramFile, 'w', os.O_NONBLOCK) as file:
						pass
					print(_('El token es incorrecto'))
					enter()
					return False
				else:
					print(_('El token es correcto.'))
					enter()
					return True
