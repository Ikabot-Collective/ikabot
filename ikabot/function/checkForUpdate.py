#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import gettext
import ikabot.config as config
from ikabot.helpers.process import run

t = gettext.translation('checkForUpdate',
                        config.localedir,
                        languages=config.idiomas,
                        fallback=True)
_ = t.gettext

def checkForUpdate():
	upgrade = run('python3 -m pip search ikabot').decode('utf-8').strip()
	if 'ikabot' not in upgrade:
		return

	upgrade = upgrade.split('\n')
	if len(upgrade) != 3:
		return

	upgrade = upgrade[2]
	match = re.search(r' +.*?: +(.*)', upgrade)
	if match is None:
		return

	new = match.group(1)
	config.update_msg = _('[+] ikabot version {} is available\n').format(new)
