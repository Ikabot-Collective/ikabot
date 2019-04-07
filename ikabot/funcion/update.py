#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
from ikabot.helpers.process import run
from ikabot.helpers.gui import *
from ikabot.config import *

t = gettext.translation('update', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def update(s):
	out = run('python3 -m pip install --upgrade ikabot').read().decode("utf-8") 
	if 'up-to-date' in out:
		print(_('\nEstá actualizado'))
	else:
		clear()
		print(_('Actualizando...\n'))
		print(out)
		print(_('Listo.'))
		print(_('Reinicie ikabot para que los cambios surjan efecto.'))
	enter()
