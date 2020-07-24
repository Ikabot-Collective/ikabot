#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import gettext
from ikabot.config import *
from ikabot.helpers.botComm import *

t = gettext.translation('signals',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def do_nothing(signal, frame):
	pass

def deactivate_sigint():
	signal.signal(signal.SIGINT, do_nothing) #signal.SIGHUP replaced with signal.SIGINT for compatibility

def create_handler(s):
	def _handler(signum, frame):
		raise Exception(_('Signal number {:d} received').format(signum))
	return _handler

def setSignalsHandlers(s):
	signals = [signal.SIGINT, signal.SIGTERM] #signal.SIGQUIT replaced with signal.SIGINT for compatibility
	for sgn in signals:
		signal.signal(sgn, create_handler(s))

def setInfoSignal(session, info): # send process info to bot
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	info : str
	"""
	info = _('information of the process {}:\n{}').format(os.getpid(), info)
	def _sendInfo(signum, frame):
		sendToBot(session, info)
	signal.signal(signal.SIGABRT, _sendInfo) # kill -SIGUSR1 pid, SIGUSR1 replaced with SIGABRT for compatibility
