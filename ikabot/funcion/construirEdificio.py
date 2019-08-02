#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import gettext
from ikabot.config import *
from ikabot.helpers.pedirInfo import elegirCiudad
#import re
#import math
#import traceback
#from decimal import *
#from ikabot.helpers.process import forkear
#from ikabot.helpers.varios import addPuntos
#from ikabot.helpers.gui import enter, banner
#from ikabot.helpers.getJson import getCiudad
#from ikabot.helpers.signals import setInfoSignal
#from ikabot.helpers.planearViajes import esperarLlegada
#from ikabot.helpers.pedirInfo import getIdsDeCiudades, read
#
#from ikabot.helpers.botComm import *
#from ikabot.helpers.recursos import *

t = gettext.translation('construirEdificio', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def construirEdificio(s):

	print(_('Ciudad donde contruir:'))
	ciudad = elegirCiudad(s)

	espacios = [ edificio for edificio in ciudad['position'] if edificio['building'] == 'empty' ]
	
	tipos = ['sea', 'land', 'shore', 'wall']
	for tipo in tipos:
		espacios_tipo = [ espacio for espacio in espacios if espacio['type'] == tipo ]
		if len(espacios_tipo) > 0:
			print(tipo)
			params = {'view': 'buildingGround', 'cityId': ciudad['id'], 'position': espacios_tipo[0]['position'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'actionRequest': s.token(), 'ajax': '1'}
			resp = s.post(params=params, noIndex=True)
			html = json.loads(resp, strict=False)[1][1][1]
			
