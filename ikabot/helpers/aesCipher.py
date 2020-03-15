#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import json
import base64
import hashlib
from ikabot.config import *
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

t = gettext.translation('aesCipher',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

class AESCipher:

	def __init__( self, mail, username, password ):
		self.key = hashlib.sha256( mail.encode('utf-8') + b'\x00' + password.encode('utf-8') ).digest()
		for i in range(0xfff):
			self.key = hashlib.sha256( self.key ).digest()

	def encrypt( self, plaintext ):
		aesgcm = AESGCM(self.key)
		nonce = os.urandom(16)
		ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
		return base64.b64encode( nonce + ciphertext ).decode('utf-8')

	def decrypt( self, ciphertext ):
		ciphertext = base64.b64decode(ciphertext)
		nonce      = ciphertext[:16]
		ciphertext = ciphertext[16:]
		aesgcm = AESGCM(self.key)
		plaintext  = aesgcm.decrypt(nonce, ciphertext, None)
		return plaintext.decode('utf-8')

def getEntryKey(s):
	return hashlib.sha256( 'ikabot'.encode('utf-8') + s.mail.encode('utf-8') ).hexdigest()

def getFileData(s, all=False):
	entry_key = getEntryKey(s)
	with open(ikaFile, 'r', os.O_NONBLOCK) as filehandler:
		ciphertexts = filehandler.read()

	for ciphertext in ciphertexts.split('\n'):
		if entry_key == ciphertext[:64]:
			ciphertext = ciphertext[64:]
			try:
				plaintext = s.cipher.decrypt(ciphertext)
			except ValueError:
				if s.padre:
					print(_('Mail o contrasenia incorrecta'))
				else:
					sendToBot(s, _('MAC check ERROR, ciphertext corrompido.'))
				os._exit(0)
			data_dict = ast.literal_eval(plaintext)
			if all is False:
				try:
					data_dict = data_dict[s.username][s.mundo][s.servidor]
				except KeyError:
					return {}
			return data_dict
	return {}

def setFileData(s, data):
	session_data = getFileData(s, True)

	if s.username not in session_data:
		session_data[s.username] = {}
	if s.mundo not in session_data[s.username]:
		session_data[s.username][s.mundo] = {}
	if s.servidor not in session_data[s.username][s.mundo]:
		session_data[s.username][s.mundo][s.servidor] = {}

	session_data[s.username][s.mundo][s.servidor] = data

	plaintext  = json.dumps(session_data)
	ciphertext = s.cipher.encrypt(plaintext)

	with open(ikaFile, 'r', os.O_NONBLOCK) as filehandler:
		data = filehandler.read()

	entry_key  = getEntryKey(s)
	newFile = ''
	for line in data.split('\n'):
		if entry_key != line[:64]:
			newFile += line + '\n'

	newFile += entry_key + ' ' + ciphertext

	with open(ikaFile, 'w', os.O_NONBLOCK) as filehandler:
		filehandler.write(newFile.strip())
		filehandler.flush()
