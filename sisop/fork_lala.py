#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sisop.run

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
