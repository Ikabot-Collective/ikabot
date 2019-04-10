#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gettext
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
from ikabot.funcion.comprarRecursos import comprarRecursos

t = gettext.translation('command_line', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

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
					comprarRecursos,
					update
					]
	print(_('(0)  Salir'))
	print(_('(1)  Lista de construcción'))
	print(_('(2)  Enviar recursos'))
	print(_('(3)  Enviar vino'))
	print(_('(4)  Estado de la cuenta'))
	print(_('(5)  Donar'))
	print(_('(6)  Buscar espacios nuevos'))
	print(_('(7)  Entrar diariamente'))
	print(_('(8)  Alertar ataques'))
	print(_('(9)  Bot donador'))
	print(_('(10) Alertar poco vino'))
	print(_('(11) Comprar recursos'))
	print(_('(12) Actualizar Ikabot'))
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
