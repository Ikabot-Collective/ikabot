#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import getpass
import os
import gettext
from ikabot.config import *
from ikabot.web.session import *
from ikabot.helpers.gui import *


def checker(session):
    session_data = session.getSessionData()
    if 'status' not in session_data:
        session_data['status'] = {}
        session_data['status']['data'] = config.default_bner
        session_data['status']['set'] = False
    else:
        session_data['status']['data'] = config.default_bner
        session_data['status']['set'] = False
    if 'cookie' not in session_data:
        session_data['cookie'] = {}
        session_data['cookie']['conf'] = ''
        session_data['cookie']['user'] = config.infoUser
        session_data['cookie']['set'] = False
    else:
        session_data['cookie']['user'] = config.infoUser
    session.setSessionData(session_data)
