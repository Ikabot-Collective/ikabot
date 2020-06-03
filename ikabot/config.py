import os
import random
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

# only use common browsers
if random.randint(0, 1) == 0:
    user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'
else:
    user_agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:77.0) Gecko/20100101 Firefox/77.0'

update_msg = ''

isWindows = os.name == 'nt'

proxy = False
if proxy:
    http_proxy  = "http://127.0.0.1:8080"
    https_proxy = "https://127.0.0.1:8080"
    proxyDict = {"http": http_proxy, "https": https_proxy}
else:
    proxyDict = {}

ids = None
ciudades = None
menuCiudades = ''
infoUser = ''
ikaFile = '.ikabot'
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
debugON_activarMilagro    = False
