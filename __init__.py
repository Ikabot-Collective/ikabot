import os
from sisop.varios import *

path = os.path.abspath(__file__)
path = os.path.dirname(path)
os.chdir(path)
run('touch ' + cookieFile)
run('touch ' + telegramFile)
