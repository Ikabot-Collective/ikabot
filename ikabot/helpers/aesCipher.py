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
        entry_key = self.getEntryKey(session)
        with open(ikaFile, "r") as filehandler:
            data = filehandler.read()

        newFile = ""
        for line in data.split("\n"):
            if entry_key != line[:64]:
                newFile += line + "\n"

        with open(ikaFile, "w") as filehandler:
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
        with open(ikaFile, "r") as filehandler:
            ciphertexts = filehandler.read()

        for ciphertext in ciphertexts.split("\n"):
            if entry_key == ciphertext[:64]:
                ciphertext = ciphertext[64:]
                try:
                    plaintext = self.decrypt(ciphertext)
                except Exception:
                    msg = "Error while decrypting session data.\nYou may have entered a wrong password."
                    
                    if session.padre:
                        print(msg)
                    else:
                        sendToBot(session, msg)
                    print("\nWould you like to delete the ikabot session data associated with this email address? [y/N]")
                    rta = read(values=["n", "N", "y", "Y"])
                    if rta.lower() == "n":
                        os._exit(0)
                    self.deleteSessionData(session)
                    os._exit(0)
                data_dict = json.loads(plaintext, strict=False)
                if all:
                    return data_dict
                else:
                    try:
                        try:
                            session_data = data_dict[session.username][session.mundo][
                                session.servidor
                            ]
                        except Exception:
                            session_data = {}
                        session_data["shared"] = data_dict["shared"]
                        return session_data
                    except KeyError:
                        return {}
        return {}

    def setSessionData(self, session, data, shared=False):
        """
        Parameters
        ----------
        session : ikabot.web.session.Session
        data : dict
        """
        session_data = self.getSessionData(session, True)

        if shared:
            if "shared" not in session_data:
                session_data["shared"] = {}
            if "logLevel" not in session_data["shared"]:
                session_data["shared"]["logLevel"] = 2  # Warn by default
            session_data["shared"] = {**session_data["shared"], **data}
        else:
            if session.username not in session_data:
                session_data[session.username] = {}
            if session.mundo not in session_data[session.username]:
                session_data[session.username][session.mundo] = {}
            if session.servidor not in session_data[session.username][session.mundo]:
                session_data[session.username][session.mundo][session.servidor] = {}
            if "shared" not in session_data:
                session_data["shared"] = {}
            session_data[session.username][session.mundo][session.servidor] = data

        plaintext = json.dumps(session_data)
        ciphertext = self.encrypt(plaintext)

        with open(ikaFile, "r") as filehandler:
            data = filehandler.read()

        entry_key = self.getEntryKey(session)
        newFile = ""
        newline = entry_key + " " + ciphertext
        for line in data.split("\n"):
            if entry_key != line[:64]:
                newFile += line + "\n"
        newFile += newline + "\n"

        with open(ikaFile, "w") as filehandler:
            filehandler.write(newFile.strip())
            filehandler.flush()
