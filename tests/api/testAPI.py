import requests
import subprocess
import time
import os
import threading
import signal
def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read()
start = time.time()
text = run('nslookup -q=txt ikabot.twilightparadox.com ns2.afraid.org').decode('utf-8').strip()
address = text.split('"')[1]

    
sum = 0
i = 0
    
def testPirateCaptchaContiniously():
    global sum
    global i
    while True:
        time.sleep(5)
        start = time.time()
        file1 = open('testpic.png','rb')
        files = {'upload_file': file1}
        captcha = requests.post('http://{0}'.format(address), files=files).text
        if 'Error' in captcha:
            print(captcha)
            break
        sum += time.time() - start
        i+=1
        print(captcha + ', time delta : ' + str(time.time() - start) )
        print('sum: ', str(sum), ' i: ', str(i))

def testPirateCaptcha():
        start = time.time()
        file1 = open('testpic.png','rb')
        files = {'upload_file': file1}
        captcha = requests.post('http://{0}'.format(address), files=files).text
        print(captcha + ', time delta : ' + str(time.time() - start) )
    
def testLoginCaptcha():
    start = time.time()
    file2 = open('text_image.png','rb')
    file3 = open('drag_icons.png','rb')
    files = {'text_image': file2, 'drag_icons': file3}
    captcha = requests.post('http://{0}'.format(address), files=files).text
    print(captcha + ', time delta : ' + str(time.time() - start))
    
    
def signal_handlerbrk(sig, frame):
    threading.Thread(target = testPirateCaptcha).start()
    print('Pirate captcha testing...')

def signal_handlerint(sig, frame):
    threading.Thread(target = testLoginCaptcha).start()
    print('Login captcha testing...')

signal.signal(signal.SIGBREAK, signal_handlerbrk)

signal.signal(signal.SIGINT, signal_handlerint)

print('break for pirate, ctrl c for login')

while True:
    time.sleep(0.5)