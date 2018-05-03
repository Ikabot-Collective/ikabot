#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import signal

def create_handler(s):
	def _handler(signum, frame):
		raise Exception('Señal recibida número {:d}'.format(signum))
	return _handler

def setSignalsHandlers(s):
	signals = [signal.SIGHUP, signal.SIGQUIT, signal.SIGABRT, signal.SIGTERM]
	for sgn in signals:
		signal.signal(sgn, create_handler(s))

def setInfoSignal(s, info): # el proceso explica su funcion por stdout
	info = '{}\n{}'.format(s.urlBase, s.username) + info
	def _printInfo(signum, frame):
		print(info)
	signal.signal(signal.SIGUSR1, _printInfo) # kill -SIGUSR1 pid
