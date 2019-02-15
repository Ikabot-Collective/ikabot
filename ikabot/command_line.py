#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from ikabot.config import *
from ikabot.web.getSesion import getSesion
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import run
from ikabot.helpers.signals import setSignalsHandlers
from ikabot.funcion.subirEdificio import subirEdificios
from ikabot.funcion.menuRutaComercial import menuRutaComercial
from ikabot.funcion.enviarVino import enviarVino
from ikabot.funcion.getStatus import getStatus
from ikabot.funcion.donar import donar
from ikabot.funcion.buscarEspacios import buscarEspacios
from ikabot.funcion.entrarDiariamente import entrarDiariamente
from ikabot.funcion.alertarAtaques import alertarAtaques
from ikabot.funcion.botDonador import botDonador
from ikabot.funcion.update import update
from ikabot.funcion.alertarPocoVino import alertarPocoVino

def menu(s):
	banner()
	menu_actions = [
					subirEdificios,
					menuRutaComercial,
					enviarVino,
					getStatus,
					donar,
					buscarEspacios,
					entrarDiariamente,
					alertarAtaques,
					botDonador,
					alertarPocoVino,
					update
					]
	mnu="""
(0)  Salir
(1)  Lista de construcción
(2)  Enviar recursos
(3)  Enviar vino
(4)  Estado de la cuenta
(5)  Donar
(6)  Buscar espacios nuevos
(7)  Entrar diariamente
(8)  Alertar ataques
(9)  Bot donador
(10) Alertar poco vino
(11) Actualizar Ikabot"""
	print(mnu)
	entradas = len(menu_actions)
	eleccion = read(min=0, max=entradas)
	if eleccion != 0:
		try:
			menu_actions[eleccion - 1](s)
		except KeyboardInterrupt:
			pass
		menu(s)
	else:
		clear()

def inicializar():
	os.chdir(os.getenv("HOME"))
	if not os.path.isfile(cookieFile):
		open(cookieFile, 'w')
		os.chmod(cookieFile, 0o600)
	if not os.path.isfile(telegramFile):
		open(telegramFile, 'w')
		os.chmod(telegramFile, 0o600)

def start():
	inicializar()
	s = getSesion()
	setSignalsHandlers(s)
	try:
		menu(s)
	finally:
		if os.fork() == 0:
			s.logout()

def main():
	try:
		start()
	except KeyboardInterrupt:
		clear()

if __name__ == '__main__':
	main()
