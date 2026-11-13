#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ikabot.config import *
from ikabot.helpers.botComm import *


class AESCipher:

    def __init__(self, mail, password):
        if type(password) == int:
            password = str(password)
        self.key = hashlib.sha256(
            mail.encode("utf-8") + b"\x00" + password.encode("utf-8")
        ).digest()
        for i in range(0xFFF):
            self.key = hashlib.sha256(self.key).digest()

    def encrypt(self, plaintext):
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(16)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    def decrypt(self, ciphertext):
        ciphertext = base64.b64decode(ciphertext)
        nonce = ciphertext[:16]
        ciphertext = ciphertext[16:]
        aesgcm = AESGCM(self.key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def getEntryKey(self, session):
        """
        Parameters
        ----------
        session : ikabot.web.session.Session

        Returns
        -------
        entry key : str
        """
        return hashlib.sha256(
            "ikabot".encode("utf-8") + session.mail.encode("utf-8")
        ).hexdigest()

    def deleteSessionData(self, session):
        """
        Parameters
        ----------
        session : ikabot.web.session.Session
        """
        from ikabot.helpers.sessionStorage import delete_session_data
        delete_session_data(session)

    def getSessionData(self, session, all=False):
        """
        Parameters
        ----------
        session : ikabot.web.session.Session
        all : bool
        """
        from ikabot.helpers.sessionStorage import get_session_data
        return get_session_data(session, all_data=all)

    def setSessionData(self, session, data, shared=False):
        """
        Parameters
        ----------
        session : ikabot.web.session.Session
        data : dict
        """
        from ikabot.helpers.sessionStorage import set_session_data
        set_session_data(session, data, shared=shared)

