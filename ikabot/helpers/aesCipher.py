#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import base64
import hashlib
from ikabot.config import *
from ikabot.helpers.botComm import *
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

t = gettext.translation('aesCipher',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

class AESCipher:

	def __init__(self, mail, username, password):
		self.key = hashlib.sha256( mail.encode('utf-8') + b'\x00' + password.encode('utf-8') ).digest()
		for i in range(0xfff):
			self.key = hashlib.sha256( self.key ).digest()

	def encrypt(self, plaintext):
		aesgcm = AESGCM(self.key)
		nonce = os.urandom(16)
		ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
		return base64.b64encode( nonce + ciphertext ).decode('utf-8')

	def decrypt(self, ciphertext):
		ciphertext = base64.b64decode(ciphertext)
		nonce      = ciphertext[:16]
		ciphertext = ciphertext[16:]
		aesgcm = AESGCM(self.key)
		plaintext  = aesgcm.decrypt(nonce, ciphertext, None)
		return plaintext.decode('utf-8')

	def getEntryKey(self, session):
		"""
		Parameters
		----------
		session : ikabot.web.session.Session

		Returns
		-------
		entry key : str
		"""
		return hashlib.sha256('ikabot'.encode('utf-8') + session.mail.encode('utf-8')).hexdigest()

	def deleteSessionData(self, session):
		"""
		Parameters
		----------
		session : ikabot.web.session.Session
		"""
		entry_key = self.getEntryKey(session)
		with open(ikaFile, 'r') as filehandler:
			data = filehandler.read()

		newFile = ''
		for line in data.split('\n'):
			if entry_key != line[:64]:
				newFile += line + '\n'

		with open(ikaFile, 'w') as filehandler:
			filehandler.write(newFile.strip())
			filehandler.flush()

	def getSessionData(self, session, all=False):
		"""
		Parameters
		----------
		session : ikabot.web.session.Session
		all : bool
		"""
		entry_key = self.getEntryKey(session)
		with open(ikaFile, 'r') as filehandler:
			ciphertexts = filehandler.read()

		for ciphertext in ciphertexts.split('\n'):
			if entry_key == ciphertext[:64]:
				ciphertext = ciphertext[64:]
				try:
					plaintext = self.decrypt(ciphertext)
				except:
					msg = _('Error while decrypting session data\nSaved data will be deleted.')
					if session.padre:
						print(msg)
					else:
						sendToBot(session, msg)
					self.deleteSessionData(session)
					os._exit(0)
				data_dict = json.loads(plaintext, strict=False)
				if all:
					return data_dict
				else:
					try:
						return data_dict[session.username][session.mundo][session.servidor]
					except KeyError:
						return {}
		return {}

	def setSessionData(self, session, data):
		"""
		Parameters
		----------
		session : ikabot.web.session.Session
		data : dict
		"""
		session_data = self.getSessionData(session, True)

		if session.username not in session_data:
			session_data[session.username] = {}
		if session.mundo not in session_data[session.username]:
			session_data[session.username][session.mundo] = {}
		if session.servidor not in session_data[session.username][session.mundo]:
			session_data[session.username][session.mundo][session.servidor] = {}

		session_data[session.username][session.mundo][session.servidor] = data

		plaintext  = json.dumps(session_data)
		ciphertext = self.encrypt(plaintext)

		with open(ikaFile, 'r') as filehandler:
			data = filehandler.read()

		entry_key  = self.getEntryKey(session)
		newFile = ''
		newline = entry_key + ' ' + ciphertext
		for line in data.split('\n'):
			if entry_key != line[:64]:
				newFile += line + '\n'
		newFile += newline + '\n'

		with open(ikaFile, 'w') as filehandler:
			filehandler.write(newFile.strip())
			filehandler.flush()
