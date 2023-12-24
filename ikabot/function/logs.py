#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import gettext
import logging
import sys
import pprint
import requests
import base64
import gzip
import io
from ikabot.helpers.pedirInfo import read, enter
from ikabot.helpers.gui import *
from ikabot.config import *

t = gettext.translation('logs', localedir, languages=languages, fallback=True)
_ = t.gettext

key = 'Cy8JNToyOz0zUltBJFo3CiIgKyc1NwMyP1kJEzUjJFgzJQsGOAAJCz5EOFY='

def logs(session, event, stdin_fd, predetermined_input):
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
    global key
    key = base64.b64decode(key).decode("utf-8")
    key = "".join([chr(ord(key[i]) ^ ord('ikabot'[i % len('ikabot')])) for i in range(len(key))])
    try:
        while True:
            banner()
            print("0) Back")
            print("1) Set log level")
            print("2) View logs")
            choice = read(min = 0, max = 2, digit = True)
            if choice == 0:
                event.set()
                return
            elif choice == 1:
                banner()
                print(
                    "The current log level is: ",
                    logging.getLevelName(logging.getLogger().getEffectiveLevel())
                )

                _levels = ['DEBUG', 'INFO', 'WARN', 'ERROR']
                for i, l in enumerate(_levels):
                    print("{}) {}".format(i, l))
                choice = read(min=0, max=len(_levels) - 1, digit=True)
                logging.getLogger().setLevel(logging.getLevelName(_levels[choice]))
                print(
                    "The log level has been set to: ",
                    logging.getLevelName(logging.getLogger().getEffectiveLevel()),
                )
                enter()
            else:    
                viewLogs(session)
                    
      
    except KeyboardInterrupt:
        event.set()
        return
    

def viewLogs(session, sort = '-date', page = 0):
    while True:

        banner()
        logs = session.getLogs(sort = sort, page = page)

        displayLogs = [
                        '[' + bcolors.RED + 'ERROR' + bcolors.ENDC + ']' + ' ' + log['date'] + ' ' + log['message'][:50].replace('\n','') if log['level'] == 3 else \
                        '[' + bcolors.WARNING + 'WARN ' + bcolors.ENDC + ']' + ' ' + log['date'] + ' ' + log['message'][:50].replace('\n','') if log['level'] == 2 else \
                        '[' + bcolors.BLUE + 'INFO ' + bcolors.ENDC + ']' + ' ' + log['date'] + ' ' + log['message'][:50].replace('\n','') if log['level'] == 1 else \
                        '[' + bcolors.GREEN + 'DEBUG' + bcolors.ENDC + ']' + ' ' + log['date'] + ' ' + log['message'][:50].replace('\n','') \
                        for log in logs ]

        printChoiceList(displayLogs)
        print("Type in the number of the log you wish to see the details of. Press enter for next page, or type in back for previous page.")
        print("To sort this list type in the property by which to sort: 'level', 'date', 'message'")
        choice = read(min = 1, max = 25, additionalValues =  ["back", "level", "date", "message", ""], empty = True)
        if str(choice).isdigit():
            viewLogDetails(session, page, choice, sort)
            viewLogs(session, sort=sort, page=page)
        elif choice == '':
            viewLogs(session, sort=sort, page=page+1)
        elif choice in ['level', 'date', 'message']:
            choice = '-'+choice if choice == sort else choice   # add - to sort so it reverses order if user typed it twice
            viewLogs(session, sort=choice, page=0)
        elif choice == 'back' and (sort != 'date' or page != 0):
            return
        else:
            pass
        

def viewLogDetails(session, page, log_number, sort):
    try:
        log = session.getLogs(page=page, sort=sort)[log_number-1]
        pprint.pprint(log, indent=4)
        print('\nPress [Enter] to upload this log dump to pastebin. Or type in back to go back\
               \nPlease beware that this log might contain identifiable information such as city, player and island ids and names.')
        choice = read(empty = True, values='back')
        if choice == 'back':
            return
        elif choice == '':
            pass
        choice = read(msg="Do you wish to ommit the request history from the log before uploading it to pastebin? [Y|n]: ", values=['n','N','Y','y'])
        if choice in ['y','Y']:
            log['request_history'] = 'None'
        print('Posting to pastebin...')
        print(post_to_pastebin(session, log))
        enter()
    except KeyboardInterrupt:
        pass

def post_to_pastebin(session, log):
    try:                                                                                                                                             

        log['request_history'] = compress_str(log['request_history'])
        response = requests.post("https://pastebin.com/api/api_post.php", data={"api_dev_key": base64.b64decode(key).decode("utf-8"), "api_option": "paste", "api_paste_code": pprint.pformat(log, indent=4)})
        assert response.status_code == 200, "Access code is not 200: {}\n text is: {}".format(response.status_code, response.text)
        return 'Access this log at ' + response.text
    except:
        return 'Error, paste failed!'
    
def compress_str(str):
    """Compresses string str and returns base64 value
    """
    s_bytes = str.encode('utf-8')
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(s_bytes)
    return base64.b64encode(out.getvalue()).decode('utf-8')

def decompress_str(str):
    """Takes in a compressed string in base64 form and decompresses and decodes it
        Use this function to decode the request history that is pasted in the pastebin!
    """
    s_bytes = base64.b64decode(str)
    inp = io.BytesIO(s_bytes)
    with gzip.GzipFile(fileobj=inp, mode='r') as f:
        decompressed_bytes = f.read()
    return decompressed_bytes.decode('utf-8')