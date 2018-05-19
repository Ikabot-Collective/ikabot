#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from config import *
from web.getSesion import getSesion
from helpers.gui import *
from helpers.pedirInfo import read
from helpers.process import run
from helpers.signals import setSignalsHandlers
from funcion.subirEdificio import subirEdificios
from funcion.menuRutaComercial import menuRutaComercial
from funcion.enviarVino import enviarVino
from funcion.getStatus import getStatus
from funcion.donar import donar
from funcion.buscarEspacios import buscarEspacios
from funcion.entrarDiariamente import entrarDiariamente
from funcion.alertarAtaques import alertarAtaques
from funcion.botDonador import botDonador
from funcion.update import update

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
					update]
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
(10) Actualizar IkaBot"""
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
	path = os.path.abspath(__file__)
	path = os.path.dirname(path)
	os.chdir(path)
	run('touch ' + cookieFile)
	run('touch ' + telegramFile)

def main():
	inicializar()
	s = getSesion()
	setSignalsHandlers(s)
	try:
		menu(s)
	except:
		raise
	finally:
		if os.fork() == 0:
			s.logout()

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		clear()
