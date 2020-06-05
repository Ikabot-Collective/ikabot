#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gettext
import multiprocessing
from ikabot.config import *
from ikabot.web.sesion import *
from ikabot.helpers.gui import *
from ikabot.funcion.donar import donar
from ikabot.funcion.update import update
from ikabot.helpers.pedirInfo import read
from ikabot.funcion.getStatus import getStatus
from ikabot.funcion.botDonador import botDonador
from ikabot.helpers.botComm import cargarTelegram
from ikabot.helpers.process import updateProcessList
from ikabot.funcion.subirEdificio import subirEdificios
from ikabot.funcion.buscarEspacios import buscarEspacios
from ikabot.funcion.alertarAtaques import alertarAtaques
from ikabot.funcion.modoVacaciones import modoVacaciones
from ikabot.funcion.activarMilagro import activarMilagro
from ikabot.funcion.entrenarTropas import entrenarTropas
from ikabot.funcion.entrenarFlotas import entrenarFlotas
from ikabot.funcion.venderRecursos import venderRecursos
from ikabot.funcion.checkForUpdate import checkForUpdate
from ikabot.funcion.repartirRecurso import repartirRecurso
from ikabot.funcion.alertarPocoVino import alertarPocoVino
from ikabot.funcion.comprarRecursos import comprarRecursos
from ikabot.funcion.entrarDiariamente import entrarDiariamente
from ikabot.funcion.menuRutaComercial import menuRutaComercial
from ikabot.funcion.construirEdificio import construirEdificio
from ikabot.funcion.movimientosNavales import movimientosNavales

t = gettext.translation('command_line', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def menu(s, checkUpdate=True):
	if checkUpdate:
		checkForUpdate()

	banner()

	processlist = updateProcessList(s)
	if len(processlist) > 0:
		print('Running tasks:')
		for process in processlist:
			if len(process['proxies']) == 0:
				proxy = ''
			else:
				proxy = 'proxy: ' + str(process['proxies'])

			print('- pid: {} task: {} {}'.format(process['pid'], process['action'], proxy))
		print('')

	menu_actions = [
					subirEdificios,
					menuRutaComercial,
					repartirRecurso,
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
	print(_('(4)  Estado de la cuenta'))
	print(_('(5)  Donar'))
	print(_('(6)  Buscar espacios nuevos'))
	print(_('(7)  Entrar diariamente'))
	print(_('(8)  Alertar ataques'))
	print(_('(9)  Donar automaticamente'))
	print(_('(10) Alertar poco vino'))
	print(_('(11) Comprar recursos'))
	print(_('(12) Vender recursos'))
	print(_('(13) Activar modo vacaciones'))
	print(_('(14) Activar milagro'))
	print(_('(15) Entrenar tropas'))
	print(_('(16) Entrenar flotas'))
	print(_('(17) Ver movimientos'))
	print(_('(18) Construir edificio'))
	print(_('(19) Actualizar Ikabot'))
	print(_('(20) Actualizar datos de Telegram'))

	entradas = len(menu_actions)
	eleccion = read(min=0, max=entradas)
	if eleccion != 0:
		try:
			eleccion -= 1
			event = multiprocessing.Event() #creates a new event
			process = multiprocessing.Process(target=menu_actions[eleccion], args=(s, event, sys.stdin.fileno()), name=menu_actions[eleccion].__name__ + s.username)
			process.start()
			processlist.append({'pid': process.pid, 'proxies': s.s.proxies, 'action': menu_actions[eleccion].__name__ })
			updateProcessList(s, programprocesslist = processlist)
			event.wait() #waits for the process to fire the event that's been given to it. When it does  this process gets back control of the command line and asks user for more input
		except KeyboardInterrupt:
			pass
		menu(s, checkUpdate=False)
	else:
		if isWindows:
			# in unix, you can exit ikabot and close the terminal and the processes will continue to execute
			# in windows, you can exit ikabot but if you close the terminal, the processes will die
			print('Closing this console will kill the processes.')
			enter()
		clear()
		os._exit(0) #kills the process which executes this statement, but it does not kill it's child processes

def inicializar():
	home = 'HOMEPATH' if isWindows else 'HOME'
	os.chdir(os.getenv(home))
	if not os.path.isfile(ikaFile):
		open(ikaFile, 'w')
		os.chmod(ikaFile, 0o600)

def start():
	inicializar()
	s = Sesion()
	try:
		menu(s)
	finally:
		clear()
		s.logout()

def main():
	try:
		start()
	except KeyboardInterrupt:
		clear()

if __name__ == '__main__':
	main()
