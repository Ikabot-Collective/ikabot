#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import re
import os
import json
import random
import gettext
import sys
import ikabot.web.session
from ikabot.config import *
import ikabot.config as config
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read

t = gettext.translation('botComm', localedir, languages=languages, fallback=True)
_ = t.gettext


def sendToBotDebug(session, msg, debugON):
    """This function will send the ``msg`` argument passed to it as a message to the user on Telegram, only if ``debugOn`` is ``True``
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    msg : str
        a string representing the message to send to the user on Telegram
    debugON : bool
        a boolean indicating whether or not to send the message.
    """
    if debugON:
        sendToBot(session, msg)


def sendToBot(session, msg, Token=False, Photo=None):
    """This function will send the ``msg`` argument passed to it as a message to the user on Telegram
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    msg : str
        a string representing the message to send to the user on Telegram
    Token : bool
        a boolean indicating whether or not to attach the process id, the users server, world and Ikariam username to the message
    Photo : bytes
        a bytes object representing a picture to be sent.
    """

    logging.info('Messaging Telegram bot: %s', msg)
    if checkTelegramData(session) is False:
        logging.error('Telegram data is not correct.')
        return
    if Token is False:
        msg = 'pid:{}\n{}\n{}'.format(os.getpid(), config.infoUser, msg)

    sessionData = session.getSessionData()
    telegram_data = sessionData['shared']['telegram']
    if Photo is None:
        ikabot.web.session.normal_get('https://api.telegram.org/bot{}/sendMessage'.format(telegram_data['botToken']), params={'chat_id': telegram_data['chatId'], 'text': msg})
    else:
        # we need to clear the headers here because telegram doesn't like keep-alive, might as well get rid of all headers
        headers = session.s.headers.copy()
        session.s.headers.clear()
        resp = session.s.post('https://api.telegram.org/bot{}/sendDocument'.format(telegram_data['botToken']), files={'document': ('captcha.png', Photo)}, data={'chat_id': telegram_data['chatId'],'caption': msg})
        session.s.headers = headers


def telegramDataIsValid(session):
    """This function checks whether or not there is any Telegram data stored in the .ikabot file
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        a boolean indicating whether or not there is any Telegram data stored in the .ikabot file

    """
    sessionData = session.getSessionData()
    try:
        return len(sessionData['shared']['telegram']['botToken']) > 0 and len(sessionData['shared']['telegram']['chatId']) > 0
    except KeyError:
        return False


def getUserResponse(session, fullResponse=False):
    """This function will retrieve a list of messages the user sent to the bot on Telegram.
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    updates : list[str]
        a list containing all the messages the user sent to the bot on Telegram
    """
    # returns messages that the user sends to the telegram bot

    if checkTelegramData(session) is False:
        return []

    sessionData = session.getSessionData()
    telegram_data = sessionData['shared']['telegram']

    try:
        updates = ikabot.web.session.normal_get('https://api.telegram.org/bot{}/getUpdates'.format(telegram_data['botToken'])).text
        updates = json.loads(updates, strict=False)
        if updates['ok'] is False:
            return []
        updates = updates['result']
        # only return messages from the chatId of our user
        if fullResponse:
            return [update['message'] for update in updates if 'message' in update and update['message']['chat']['id'] == int(telegram_data['chatId'])]
        else:
            return [update['message']['text'] for update in updates if 'message' in update and update['message']['chat']['id'] == int(telegram_data['chatId'])]
    except KeyError:
        return []


def checkTelegramData(session):
    """This function doesn't actually check any data itself, that is done by the ``telegramDataIsValid`` function. This function returns ``True`` if there is any Telegram data in the .ikabot file, and if there is none, it will ask the user to input it.
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    valid : bool
        a boolean indicating whether or not there is valid Telegram data in the .ikabot file.
    """
    if telegramDataIsValid(session):
        return True
    else:
        banner()
        print(_('You must provide valid credentials to communicate by telegram.'))
        print(_('You require the token of the bot you are going to use and your chat_id'))
        print(_('For more information about how to obtain them read the readme at https://github.com/physics-sp/ikabot'))
        rta = read(msg=_('Will you provide the credentials now? [y/N]'), values=['y', 'Y', 'n', 'N', ''])
        if rta.lower() != 'y':
            return False
        else:
            return updateTelegramData(session)


def updateTelegramData(session, event=None, stdin_fd=None, predetermined_input=[]):
    """This function asks the user to input the Telegram bot's token and the user's own Telegram chat id. After the user has inputted the neccessary data, this function will generate a random 4 digit number, send it to the user as a Telegram message using the token the user provided. It will then ask the user to input that number as validation.
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    event : multiprocessing.Event
        an event which, when fired, gives back control of the terminal to the main process
    stdin_fd : int
        the standard input file descriptor passed to the function as a means of gaining control of the terminal
    predetermined_input : multiprocessing.managers.SyncManager.list
        a process synced list of predetermined inputs

    Returns
    -------
    valid : bool
        a boolean indicating whether or not the Telegram data has been successfully updated
    """
    if event is not None and stdin_fd is not None:
        sys.stdin = os.fdopen(stdin_fd)  # give process access to terminal
    config.predetermined_input = predetermined_input
    banner()
    print(_('To create your own Telegram Bot, read this: https://core.telegram.org/bots#3-how-do-i-create-a-bot'))
    print(_('Just talk to @botfather in Telegram, send /newbot and then choose the bot\'s name.'))
    print(_('Talk to your new bot and send /start'))
    print(_('Remember to keep the token secret!\n'))
    botToken = read(msg=_('Bot\'s token:'))

    updates = ikabot.web.session.normal_get('https://api.telegram.org/bot{}/getUpdates'.format(botToken)).json()
    if 'ok' not in updates or updates['ok'] is False:
        print(_('invalid telegram bot, try again.'))
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False

    user_ids = []
    users = []
    for update in updates['result']:
        if 'message' in update:
            user = update['message']['from']
            if user['id'] not in user_ids and 'username' in user:
                users.append(user)
                user_ids.append(user['id'])

    if len(users) == 0:
        print(_('make sure your personal Telegram account has a username configured and then send a random message to your bot'))
        enter()
        if event is not None and stdin_fd is not None:
            event.set()
        return False
    elif len(users) == 1:
        resp = read(msg=_('is your username {}? [Y/n]').format(users[0]['username']), default='y', values=['y', 'Y', 'N', 'n'])
        if resp.lower() == 'n':
            print(_('talk to your bot and try again'))
            if event is not None and stdin_fd is not None:
                event.set()
            return False
        else:
            chat_id = users[0]['id']
    else:
        print(_('select your username:'))
        print(_('0) My username is not listed'))
        for i, user in enumerate(users):
            print(_('{:d}) {}').format(i+1, user['username']))
        resp = read(min=0, max=len(users))
        if resp == 0:
            print(_('talk to your bot and try again'))
            if event is not None and stdin_fd is not None:
                event.set()
            return False
        else:
            chat_id = users[resp - 1]['id']

    telegram_data = {}
    telegram_data['telegram'] = {}
    telegram_data['telegram']['botToken'] = botToken.replace(' ', '')
    telegram_data['telegram']['chatId'] = str(chat_id)
    session.setSessionData(telegram_data, shared=True)

    rand = str(random.randint(0, 9999)).zfill(4)
    msg = _('The token is:{}').format(rand)
    sendToBot(session, msg, Token=True)

    rta = read(msg=_('A message was sent by telegram, did you receive it? [Y/n]'), values=['y', 'Y', 'n', 'N', ''])
    if rta.lower() == 'n':
        valid = False
    else:
        recibido = read(msg=_('Enter the received token in telegram:'))
        if rand != recibido:
            print(_('The token is incorrect'))
            valid = False
        else:
            print(_('The token is correct'))
            valid = True

    if valid is False:
        telegram_data['telegram']['botToken'] = ''
        telegram_data['telegram']['chatId'] = ''
        session.setSessionData(telegram_data, shared=True)
        print(_('Check the credentials and re-supply them.'))
    else:
        print(_('The data was saved.'))
    enter()

    if event is not None and stdin_fd is not None:
        event.set()  # give main process control before exiting
    return valid

