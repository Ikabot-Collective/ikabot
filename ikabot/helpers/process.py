#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import multiprocessing
from ikabot.helpers.signals import deactivate_sigint

def forkear(s):
	newpid = 0 #this is because we're expecing to already be in the child process at this point
	pid = multiprocessing.current_process().pid
	if newpid != 0:
		# padre
		newpid = str(newpid)
		run('kill -SIGSTOP ' + newpid) 				#UNREACHABLE CODE, clean up later
		run('bg ' + newpid)
		run('disown ' + newpid)
	else:
		# hijo
		s.padre = False
		# if the environment is unix, then run commands to detach the current process and send to background
#		run('kill -SIGSTOP ' + pid) 				#UNREACHABLE CODE, clean up later
#		run('bg ' + pid)
#		run('disown ' + pid)
		deactivate_sigint()
		s.login()

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
