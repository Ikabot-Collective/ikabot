import os
import random
import locale
import gettext
from fake_useragent import UserAgent

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

user_agent = UserAgent()
# only use common browsers
if random.randint(0, 1) == 0:
	user_agent = user_agent.chrome
else:
	user_agent = user_agent.firefox
update_msg = ''
isWindows = os.name == 'nt'
proxy = False
proxyDict = {}
if proxy:
    http_proxy  = "http://127.0.0.1:8080"
    https_proxy = "https://127.0.0.1:8080"
    proxyDict = {"http": http_proxy, "https": https_proxy}
secure_traffic = True
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

