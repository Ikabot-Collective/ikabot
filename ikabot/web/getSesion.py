#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import gettext
import getpass
import ikabot.config as config
from ikabot.web.sesion import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import banner

t = gettext.translation('getSesion', 
                        config.localedir, 
                        languages=config.idiomas,
                        fallback=True)
_ = t.gettext

def getSesion():
	return Sesion()
