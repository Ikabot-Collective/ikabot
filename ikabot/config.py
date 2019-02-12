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
debugON_alertarAtaques    = False
debugON_alertarPocoVino   = False
debugON_botDonador        = False
debugON_buscarEspacios    = False
debugON_entrarDiariamente = False
debugON_enviarVino        = False
debugON_menuRutaComercial = False
debugON_subirEdificio     = False
debugON_session           = False
