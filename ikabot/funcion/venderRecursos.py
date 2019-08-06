#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.tienda import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import forkear
from ikabot.helpers.varios import addPuntos
#import re
#import math
#import json
#from decimal import *
#from ikabot.helpers.getJson import getCiudad
#from ikabot.helpers.signals import setInfoSignal
#from ikabot.helpers.planearViajes import esperarLlegada
#from ikabot.helpers.recursos import *

t = gettext.translation('venderRecursos', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def venderRecursos(s):
	banner()

	print(_('¿Qué recurso quiere vender?'))
	for indice, bien in enumerate(tipoDeBien):
		print('({:d}) {}'.format(indice+1, bien))
	eleccion = read(min=1, max=5)
	recurso = eleccion - 1
	banner()

	ciudades_comerciales = getCiudadesComerciales(s)
	if len(ciudades_comerciales) == 0:
		print(_('No hay una Tienda contruida'))
		enter()
		return

	ciudad = ciudades_comerciales[0] # por ahora solo uso la primera ciudad
	params = {'view': 'branchOfficeOwnOffers', 'activeTab': 'tab_branchOfficeOwnOffers', 'cityId': ciudad['id'], 'position': ciudad['pos'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'branchOfficeOwnOffers', 'currentTab': 'tab_branchOfficeOwnOffers', 'actionRequest': s.token(), 'ajax': '1'}
	resp = s.post(params=params, noIndex=True)
	html = json.loads(resp, strict=False)[1][1][1]
	cap_venta = getCapacidadDeVenta(html)
	recurso_disp = ciudad['recursos'][recurso]
	print(_('¿Cuánto quiere vender? [max = {:d}]'.format(recurso_disp)))
	vender = read(min=0, max=recurso_disp)
	print(_('Se venderá {:d} de {}').format(vender, tipoDeBien[recurso]))
	enter()

	forkear(s)
	if s.padre is True:
		return

	info = _('\nVendo {} de {}\n').format(addPuntos(vender), tipoDeBien[recursos])
	setInfoSignal(s, info)
	try:
		do_it(s, vender, recurso, cap_venta, ciudad)
	except:
		msg = _('Error en:\n{}\nCausa:\n{}').format(info, traceback.format_exc())
		sendToBot(msg)
	finally:
		s.logout()

def do_it(s, vender, recurso, cap_venta, ciudad):
	pass
