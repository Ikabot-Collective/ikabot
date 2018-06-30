#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.helpers.process import run
from ikabot.helpers.gui import *

def update(s):
	out = run('python3 -m pip install --upgrade ikabot').read().decode("utf-8") 
	if 'up-to-date' in out:
		print('\nEstá actualizado')
	else:
		clear()
		print('Actualizando...\n')
		print(out)
		print('Listo.')
		print('Reinicie ikabot para que los cambios surjan efecto.')
	enter()
