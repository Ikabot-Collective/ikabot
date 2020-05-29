#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gettext
import multiprocessing
from ikabot.config import *
from ikabot.web.sesion import *
from ikabot.helpers.gui import *
from ikabot.helpers.process import run
from ikabot.funcion.donar import donar
from ikabot.funcion.update import update
from ikabot.helpers.pedirInfo import read
from ikabot.funcion.getStatus import getStatus
from ikabot.funcion.botDonador import botDonador
from ikabot.helpers.botComm import cargarTelegram
from ikabot.helpers.signals import setSignalsHandlers
from ikabot.funcion.subirEdificio import subirEdificios
from ikabot.funcion.buscarEspacios import buscarEspacios
from ikabot.funcion.alertarAtaques import alertarAtaques
from ikabot.funcion.modoVacaciones import modoVacaciones
from ikabot.funcion.activarMilagro import activarMilagro
from ikabot.funcion.entrenarTropas import entrenarTropas
from ikabot.funcion.entrenarFlotas import entrenarFlotas
from ikabot.funcion.venderRecursos import venderRecursos
from ikabot.funcion.repartirRecurso import repartirRecurso
from ikabot.funcion.alertarPocoVino import alertarPocoVino
from ikabot.funcion.comprarRecursos import comprarRecursos
from ikabot.funcion.entrarDiariamente import entrarDiariamente
from ikabot.funcion.menuRutaComercial import menuRutaComercial
from ikabot.funcion.construirEdificio import construirEdificio
from ikabot.funcion.movimientosNavales import movimientosNavales
from ikabot.funcion.distributeResourcesEvenly import distributeResourcesEvenly

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
					repartirRecurso,
					distributeResourcesEvenly,
					getStatus,
					donar,
					buscarEspacios,
					entrarDiariamente,
					alertarAtaques,
					botDonador,
					alertarPocoVino,
					comprarRecursos,
					venderRecursos,
					modoVacaciones,
					activarMilagro,
					entrenarTropas,
					entrenarFlotas,
					movimientosNavales,
					construirEdificio,
					update,
					cargarTelegram
					]
	print(_('(0)  Salir'))
	print(_('(1)  Lista de construcción'))
	print(_('(2)  Enviar recursos'))
	print(_('(3)  Distribuir recursos'))
	print(_('(4)  Distribuir recursos uniformemente'))
	print(_('(5)  Estado de la cuenta'))
	print(_('(6)  Donar'))
	print(_('(7)  Buscar espacios nuevos'))
	print(_('(8)  Entrar diariamente'))
	print(_('(9)  Alertar ataques'))
	print(_('(10) Donar automaticamente'))
	print(_('(11) Alertar poco vino'))
	print(_('(12) Comprar recursos'))
	print(_('(13) Vender recursos'))
	print(_('(14) Activar modo vacaciones'))
	print(_('(15) Activar milagro'))
	print(_('(16) Entrenar tropas'))
	print(_('(17) Entrenar flotas'))
	print(_('(18) Ver movimientos'))
	print(_('(19) Construir edificio'))
	print(_('(20) Actualizar Ikabot'))
	print(_('(21) Actualizar datos de Telegram'))
	entradas = len(menu_actions)
	eleccion = read(min=0, max=entradas)
	processes = {} #creates dict of processes. It will look like this {entrynumber : relatedprocess, entrynumber : relatedprocess ...}
	events = {} #creates dict of events. It will look like this {entrynumber : relatedevent, entrynumber : relatedevent ...}
	if eleccion != 0:
		try:
			events.update({eleccion-1 : multiprocessing.Event()}) #inserts a new event into the dict
			processes.update({eleccion-1 : multiprocessing.Process(target=menu_actions[eleccion-1], args=(s, events[eleccion-1], sys.stdin.fileno()))}) #inserts a new process into the dict. The process is passed s, the event that's made above and stdin so it can read from command line
			processes[eleccion-1].start() #starts the process at the selected function
			events[eleccion-1].wait() #waits for the process to fire the event that's been given to it. When it does  this process gets back control of the command line and asks user for more input
#			menu_actions[eleccion - 1](s)
		except KeyboardInterrupt:
			pass

		menu(s)
	else:
		clear()

def inicializar():
	try:
		os.chdir(os.getenv("HOME"))
	except TypeError:
		os.chdir(os.getenv("HOMEPATH"))
	if not os.path.isfile(ikaFile):
		open(ikaFile, 'w')
		os.chmod(ikaFile, 0o600)

def start():
	inicializar()
	s = Sesion()
	setSignalsHandlers(s)
	try:
		menu(s)
	finally:
		s.logout()

def main():
	try:
		start()
	except KeyboardInterrupt:
		clear()

if __name__ == '__main__':
	main()
