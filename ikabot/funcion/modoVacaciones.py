#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCiudad

t = gettext.translation('modoVacaciones',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def activarModoVacaciones(s):
	html = s.get()
	ciudad = getCiudad(html)

	data = {'action': 'Options', 'function': 'activateVacationMode', 'actionRequest': s.token(), 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'options_umod_confirm'}
	s.post(params=data, ignoreExpire=True)

def modoVacaciones(s):
	banner()
	print(_('¿Activar modo vacaciones? [Y/n]'))
	rta = read(values=['y', 'Y', 'n', 'N', ''])
	if rta.lower() == 'n':
		return

	activarModoVacaciones(s)

	print(_('Se activo el modo vacaciones.'))
	enter()
	clear()
	exit()
