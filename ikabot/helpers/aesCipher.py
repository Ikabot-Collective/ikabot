#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import base64
from Crypto.Cipher import AES

class AESCipher:

	def __init__( self, key ):
		self.key = hashlib.sha256(key.encode('utf-8')).digest()

	def encrypt( self, plaintext ):
		cipher          = AES.new(self.key, AES.MODE_EAX)
		nonce           = cipher.nonce
		ciphertext, tag = cipher.encrypt_and_digest( plaintext.encode() )
		return base64.b64encode( nonce + tag + ciphertext ).decode('utf-8')

	def decrypt( self, ciphertext ):
		ciphertext = base64.b64decode(ciphertext)
		nonce      = ciphertext[:16]
		ciphertext = ciphertext[16:]
		tag        = ciphertext[:16]
		ciphertext = ciphertext[16:]
		cipher     = AES.new(self.key, AES.MODE_EAX, nonce=nonce)
		return cipher.decrypt_and_verify( ciphertext, tag ).decode('utf-8')
