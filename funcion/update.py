#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from sisop.varios import *

def update(s):
	out = run('git pull').read().decode("utf-8") 
	if 'Already up' in out:
		print('\nEstá actualizado')
	else:
		clear()
		print('Actualizando...\n')
		print(out)
		print('Listo.')
		print('Reinicie el preceso para que los cambios surjan efecto.')
	enter()
