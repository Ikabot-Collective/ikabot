#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess

def forkear(s):
	newpid = os.fork()
	if newpid != 0:
		# padre
		newpid = str(newpid)
		run('kill -SIGSTOP ' + newpid)
		run('bg ' + newpid)
		run('disown ' + newpid)
	else:
		# hijo
		s.padre = False
		s.login()

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
