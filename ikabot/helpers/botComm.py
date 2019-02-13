#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import random
import ikabot.config as config
import ikabot.web.sesion
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import enter

def sendToBotDebug(msg, debugON):
	if debugON:
		sendToBot(msg)

def sendToBot(msg, Token=False):
	if Token is False:
		msg = '{}\n{}'.format(config.infoUser, msg)
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
		print('Debe proporcionar las credenciales válidas para comunicarse por telegram.')
		print('Se requiere del token del bot a utilizar y de su chat_id')
		print('Para más informacion sobre como obtenerlos vea al readme de https://github.com/physics-sp/ikabot')
		rta = read(msg='¿Porporcionará las credenciales ahora? [y/N]', values=['y','Y','n', 'N', ''])
		if rta.lower() != 'y':
			return False
		else:
			botToken = read(msg='Token del bot:')
			chat_id = read(msg='Chat_id:')
			with open(config.telegramFile, 'w', os.O_NONBLOCK) as filehandler:
				filehandler.write(botToken + '\n' + chat_id)
				filehandler.flush()
			rand = random.randint(1000, 9999)
			msg = 'El token a ingresar es:{:d}'.format(rand)
			sendToBot(msg, Token=True)
			rta = read(msg='Se envio un mensaje por telegram, ¿lo recibió? [Y/n]', values=['y','Y','n', 'N', ''])
			if rta.lower() == 'n':
				with open(config.telegramFile, 'w', os.O_NONBLOCK) as file:
					pass
				print('Revíse las credenciales y vuelva a proveerlas.')
				enter()
				return False
			else:
				recibido = read(msg='Ingrese el token recibido mediante telegram:', digit=True)
				if rand != recibido:
					with open(config.telegramFile, 'w', os.O_NONBLOCK) as file:
						pass
					print('El token es incorrecto')
					enter()
					return False
				else:
					print('El token es correcto.')
					enter()
					return True
