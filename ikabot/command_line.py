#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gettext
from ikabot.config import *
from ikabot.web.sesion import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import run
from ikabot.helpers.signals import setSignalsHandlers
from ikabot.funcion.subirEdificio import subirEdificios
from ikabot.funcion.menuRutaComercial import menuRutaComercial
from ikabot.funcion.repartirRecurso import repartirRecurso
from ikabot.funcion.getStatus import getStatus
from ikabot.funcion.donar import donar
from ikabot.funcion.buscarEspacios import buscarEspacios
from ikabot.funcion.entrarDiariamente import entrarDiariamente
from ikabot.funcion.alertarAtaques import alertarAtaques
from ikabot.funcion.botDonador import botDonador
from ikabot.funcion.update import update
from ikabot.funcion.alertarPocoVino import alertarPocoVino
from ikabot.funcion.comprarRecursos import comprarRecursos
from ikabot.funcion.modoVacaciones import modoVacaciones
from ikabot.funcion.activarMilagro import activarMilagro
from ikabot.funcion.entrenarTropas import entrenarTropas
from ikabot.funcion.entrenarFlotas import entrenarFlotas
from ikabot.funcion.movimientosNavales import movimientosNavales
from ikabot.funcion.construirEdificio import construirEdificio
from ikabot.funcion.venderRecursos import venderRecursos

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
					update
					]
	print(_('(0)  Salir'))
	print(_('(1)  Lista de construcción'))
	print(_('(2)  Enviar recursos'))
	print(_('(3)  Repartir recurso'))
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
		if os.fork() == 0:
			s.logout()

def main():
	try:
		start()
	except KeyboardInterrupt:
		clear()

if __name__ == '__main__':
	main()
