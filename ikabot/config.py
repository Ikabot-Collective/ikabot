import getpass

ids = None
ciudades = None
infoUser = ''
cookieFile = '/tmp/.cookies_of_{}.txt'.format(getpass.getuser())
telegramFile = '/tmp/.telegram_of_{}.txt'.format(getpass.getuser())
urlCiudad = 'view=city&cityId='
urlIsla = 'view=island&islandId='
prompt = ' >>  '
tipoDeBien = ['Madera', 'Vino', 'Marmol', 'Cristal', 'Azufre']
