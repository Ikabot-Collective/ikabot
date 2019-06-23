import os
import locale
import gettext

local = locale.setlocale(locale.LC_ALL, '')
if 'es_' in local:
	idiomas = ['es']
else:
	idiomas = ['en']

localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
t = gettext.translation('config', 
                        localedir, 
                        languages=idiomas,
                        fallback=True)
_ = t.gettext


http_proxy  = "http://127.0.0.1:8080"
https_proxy = "https://127.0.0.1:8080"
proxyDict = {"http": http_proxy, "https": https_proxy}
proxyDict = {}
secure_traffic = True
ids = None
ciudades = None
menuCiudades = ''
infoUser = ''
cookieFile = '.cookies.ika'
telegramFile = '.telegram.ika'
urlCiudad = 'view=city&cityId='
urlIsla = 'view=island&islandId='
prompt = ' >>  '
tipoDeBien = [_('Madera'), _('Vino'), _('Marmol'), _('Cristal'), _('Azufre')]
ConnectionError_wait = 5 * 60
debugON_alertarAtaques    = False
debugON_alertarPocoVino   = False
debugON_botDonador        = False
debugON_buscarEspacios    = False
debugON_entrarDiariamente = False
debugON_enviarVino        = False
debugON_menuRutaComercial = False
debugON_subirEdificio     = False
debugON_session           = False
debugON_comprarRecursos   = False
