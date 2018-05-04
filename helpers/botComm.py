#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import random
from config import *
from web.sesion import get
from helpers.pedirInfo import read
from helpers.gui import enter

def sendToBot(s, msg, Token=False):
	if Token is False:
		msg = '{}\n{}'.format(infoUser, msg)
	with open(telegramFile, 'r') as filehandler:
		text = filehandler.read()
		(botToken, chatId) = text.splitlines()
		get('https://api.telegram.org/bot{}/sendMessage'.format(botToken), params={'chat_id': chatId, 'text': msg})

def botValido(s):
	with open(telegramFile, 'r') as filehandler:
		text = filehandler.read()
	rta = re.search(r'\d{6,}:[A-Za-z0-9_-]{34,}\n\d{8,9}', text)
	if rta is None:
		print('Debe proporcionar las credenciales válidas para comunicarse por telegram.')
		print('Se requiere del token del bot a utilizar y de su chat_id')
		print('El token se le proporciona al momento de crear el bot, para averiguar su chat_id, hablele por telegram a @get_id_bot')
		rta = read(msg='Porporcionará las credenciales ahora? [y/N]')
		if rta.lower() == 'y':
			botToken = read(msg='Token del bot:')
			chat_id = read(msg='Char_id:')
			with open(telegramFile, 'w') as filehandler:
				filehandler.write(botToken + '\n' + chat_id)
		else:
			return False
	rand = random.randint(1000, 9999)
	sendToBot(s, 'El token a ingresar es:{:d}'.format(rand), Token=True)
	print('Se envio un mensaje por telegram, lo recibió? [Y/n]')
	rta = read()
	if rta.lower() == 'n':
		with open(telegramFile, 'w') as file:
			pass
		print('Revíse las credenciales y vuelva a proveerlas.')
		enter()
		return False
	else:
		recibido = read(digit=True, msg='Ingrese el token recibido mediante telegram:')
		if rand != recibido:
			print('Token incorrecto')
			enter()
			return False
		else:
			print('El token es correcto.')
			return True