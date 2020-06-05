#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import gettext
from ikabot.config import *
from ikabot.helpers.botComm import *

t = gettext.translation('signals', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def do_nothing(signal, frame):
	pass

def deactivate_sigint():
	signal.signal(signal.SIGINT, do_nothing) #signal.SIGHUP replaced with signal.SIGINT for compatibility
	signal.signal(signal.SIGINT, do_nothing)

def create_handler(s):
	def _handler(signum, frame):
		raise Exception(_('Signal number {:d} received').format(signum))
	return _handler

def setSignalsHandlers(s):
	signals = [signal.SIGINT, signal.SIGABRT] #signal.SIGQUIT replaced with signal.SIGINT for compatibility, SIGTERM removed at the end of list
	for sgn in signals:
		signal.signal(sgn, create_handler(s))

def setInfoSignal(s, info): # el proceso explica su function por stdout
	info = _('information of the process {}:\n{}').format(os.getpid(), info)
	def _sendInfo(signum, frame):
		sendToBot(s, info)
	signal.signal(signal.SIGTERM, _sendInfo) # kill -SIGUSR1 pid, SIGUSR1 replaced with SIGTERM
