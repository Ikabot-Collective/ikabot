#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import gettext
import requests
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.gui import *
import ikabot.config as config

t = gettext.translation('proxy', config.localedir, languages=config.languages, fallback=True)
_ = t.gettext


def show_proxy(session):
	session_data = session.getSessionData()
	msg = _('using proxy:')
	if 'proxy' in session_data['shared'] and session_data['shared']['proxy']['set'] is True:
		proxy_data = session_data['shared']
		curr_proxy = proxy_data['proxy']['conf']['https']
		if test_proxy(proxy_data['proxy']['conf']) is False:
			proxy_data['proxy']['set'] = False
			session.setSessionData(proxy_data, shared=True)
			sys.exit(_('the {} proxy does not work, it has been removed').format(curr_proxy))
		if msg not in config.update_msg:
			# add proxy message
			config.update_msg += '{} {}\n'.format(msg, curr_proxy)
		else:
			# delete old proxy message
			config.update_msg = config.update_msg.replace('\n'.join(config.update_msg.split('\n')[-2:]), '')
			# add new proxy message
			config.update_msg += '{} {}\n'.format(msg, curr_proxy)
	elif msg in config.update_msg:
		# delete old proxy message
		config.update_msg = config.update_msg.replace('\n'.join(config.update_msg.split('\n')[-2:]), '')


def test_proxy(proxy_dict):
	try:
		requests.get('https://lobby.ikariam.gameforge.com/', proxies=proxy_dict)
	except Exception:
		return False
	return True


def read_proxy():
	print(_('Enter the proxy (examples: socks5://127.0.0.1:9050, https://45.117.163.22:8080):'))
	proxy_str = read(msg='proxy: ')
	proxy_dict = {'http': proxy_str, 'https': proxy_str}
	if test_proxy(proxy_dict) is False:
		print(_('The proxy does not work.'))
		enter()
		return None
	print(_('The proxy works and it will be used for all future requests.'))
	enter()
	return proxy_dict


def proxyConf(session, event, stdin_fd, predetermined_input):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	predetermined_input : multiprocessing.managers.SyncManager.list
	"""
	sys.stdin = os.fdopen(stdin_fd)
	config.predetermined_input = predetermined_input
	try:
		banner()
		print(_('Warning: The proxy does not apply to the requests sent to the lobby!\n'))

		session_data = session.getSessionData()
		proxy_data = {}
		proxy_data['proxy'] = {}
		if 'proxy' not in session_data['shared'] or session_data['shared']['proxy']['set'] is False:
			print(_('Right now, there is no proxy configured.'))
			proxy_dict = read_proxy()
			if proxy_dict is None:
				event.set()
				return
			proxy_data['proxy']['conf'] = proxy_dict
			proxy_data['proxy']['set'] = True
		else:
			curr_proxy = session_data['shared']['proxy']['conf']['https']
			print(_('Current proxy: {}').format(curr_proxy))
			print(_('What do you want to do?'))
			print(_('0) Exit'))
			print(_('1) Set a new proxy'))
			print(_('2) Remove the current proxy'))
			rta = read(min=0, max=2)

			if rta == 0:
				event.set()
				return
			if rta == 1:
				proxy_dict = read_proxy()
				if proxy_dict is None:
					event.set()
					return
				proxy_data['proxy']['conf'] = proxy_dict
				proxy_data['proxy']['set'] = True
			if rta == 2:
				proxy_data['proxy']['conf'] = {}
				proxy_data['proxy']['set'] = False
				print(_('The proxy has been removed.'))
				enter()

		session.setSessionData(proxy_data, shared=True)
		event.set()
	except KeyboardInterrupt:
		event.set()
		return
