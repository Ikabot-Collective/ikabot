#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import getpass
import os
import subprocess

prompt = ' >>  '

def enter():
	getpass.getpass('\n[Enter]')

def clear():
	os.system('clear')

def forkear(s):
	newpid = os.fork()
	if newpid != 0:
		# padre
		s.login()
		newpid = str(newpid)
		run('kill -SIGSTOP ' + newpid)
		run('bg ' + newpid)
		run('disown ' + newpid)
	else:
		# hijo
		s.padre = False

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

def read(min=None, max=None, digit=False, msg=prompt, values=None): # lee input del usuario
	def _invalido():
		sys.stdout.write('\033[F\r') # Cursor up one line
		blank = ' ' * len(str(leido) + msg)
		sys.stdout.write('\r' + blank + '\r')
		return read(min, max, digit, msg, values)

	try:
		leido = input(msg)
	except EOFError:
		return _invalido()

	if digit is True or min is not None or max is not None:
		if leido.isdigit() is False:
			return _invalido()
		else:
			try:
				leido = eval(leido)
			except SyntaxError:
				return _invalido()
	if min is not None and leido < min:
		return _invalido()
	if max is not None and leido > max:
		return _invalido()
	if values is not None and leido not in values:
		return _invalido()
	return leido
