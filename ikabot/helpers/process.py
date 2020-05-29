#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
from ikabot.helpers.signals import deactivate_sigint

def forkear(s):
	newpid = 0 #this is because we're expecing to already be in the child process at this point
	if newpid != 0:
		# padre
		newpid = str(newpid)
		run('kill -SIGSTOP ' + newpid) 				#UNREACHABLE CODE, clean up later
		run('bg ' + newpid)
		run('disown ' + newpid)
	else:
		# hijo
		s.padre = False
		deactivate_sigint()
		s.login()

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
