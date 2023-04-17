#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import json
import time
import random
import getpass
import datetime
import gettext
import requests
import base64
from ikabot import config
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import banner
from ikabot.helpers.aesCipher import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCity
from urllib3.exceptions import InsecureRequestWarning

t = gettext.translation('session', localedir, languages=languages, fallback=True)
_ = t.gettext

#blackbox tokens
blackbox_tokens = [
    'JVqc1PkrbpPF9zyxI5ICZ4y-BFe4Kov1WtA_ZJbI7R9ih7nrYM5BsRZ54kixFnqf0QMoWp3C9CZt0jWgDzRmmL3vMleJuxJ76U28M6bL_S9UhsnuIFKYAXPYPq0lSnyu0wVIbZ_R9ihaf7H0JEl7vvIXSYyx4xV66BVqveIUV7wqT4Gz2ApNcqTWPHCn2j5yqdwMPXDUCUGkCW6l3RRHed4XToLmSn7fRXfcFHio2Qk-cqbfQnWt4RdMhOdJr-AVRXrfE0OoDHGm1vstX4S2-R5Qgsk4pw563wQ2Zq8dgK7TBTVdnusvWH2v8jOByBRZfrDgCEmW2v8xdJnL-02uEnfmVHmr2y1mi73tH09_pNYGWb4wmf5xlsj4PKUXfN9Thsr7LFGDsymc-zCPv-QWRrYpiL0cTHWazP4jVZi97yFUiO4ihb0fT4S4HFGE6Eyu4hV3qNo_ogU-btI3bZ7SBWbIATdupgs7bqfYCTudAWPFKlu_IYbqS3uz6h6BtOkfRHaozf9CZ5nL-13D-1yMwSJZvB1VhrnyKYvsIVOK602v4UJ5ruRJea_lGk6y6RpLg7obf7LmFnms4xh94hh930GkCECj2xRGdpvN_yRWmcoDNWWKvP8wYJTE6RtekMTpG17SRLkeQ3W4LJ4TeJ3PEjdpm8wyYpX3LmXLL5DD9i1hk8X7LI7zVIToGlG27CBShedNf7EVR6kPRHvhRqgLQHPUOXClB0B2qA5Eqd4QQ6YJOWuQwvQZS46z5Rd6sedMfrATdqwNbqcNQqPZDkd_uOkiWo3vJl3AJFSMwSJVi77yVrrwVozF-DBomtEylMkqXsH3WpDBIliKwidcgbPlCjx_pNYIbqHZO50CZZrL_C2S9ixcjO1OhrbvUYW27SZewSJXju8niOwjVbnxJ1eJuexNhOggWLnvH1iM8CWJviBVuhuBtdoMPmOV2P0vYZnPMZb7XML0Wo2-91yPvyFYvCKH606EuRx_4RpKfN0WTofoGkt74Uep3EB0qt4WebHhQ6fXEEJz1DVlxvgxZJa77R9EdrnsIU-GufEkVo_E_TBgmcv9IlSXvO4gg7UWTrPoSX2tD0By1jdr0QJknP8zmfowYZfNMmmiAztvpQptptY3m9EBNGXG-i2OxCdgkMctY5TK_S5ewSaKvuMVR2ye4RJLe63lGEiAsOcMPoGm2Ao8bJ7R_i5hjsD0SHmr0ANEdq7TBkd3p9UIO3TO8yVXfK7xFkh640y98GOazC-hEkW_MJX-Ysw-d-IYjweB9WibwPIkSXu-8SdXfK7xFkh6q9sAMmSJu_4jVYfeV6jgQ70KdL8Sersel9kyhvRNxCVr0yCG3BV80Emj2i9fmAFShPxVuv43kPFboBdqsvhAkNQplOAzhP1itQtVpPhFfNUcZd4rmfxougBw0ylx1PkrccDzWozYRY76Q5bYHW_HOqv4T7Mjhcn-Zcsfh-BEsOU4gvxKnOVTvjOYyDNqzTiF90eKy0OR-16T4UukG2quEUaTDXTtEkR2m80QNWeZ5lXPOKQQcZbIDkNxocb4KFCnEH7iUcg7YJLCEGSJu-scTHqqzwJEaZvLIov5L2OIu_0iVIT8MmaLvgAlV4f5b5THCDlpotAAKU6AsPdcvyqZvvA2aJjJ-SlairvgEkKI8WPILp0VOmyy4xRFc6PI-ixRg8brHU-BseMWQ3Om0wU5jb7wFUiJu_MYS4y87BpKeqoEKVuNsuQnlQp24gc8gA',
    'JVqc1PkrbpPF9zyxI5ICZ4y-BFe4Kov1WtA_ZJbI7R9ih7nrHEFzpcr8P2SWyA9010Kx1gg6X5HU-StdtB2L717VSG2f0fYoa5DC9DqjFXrgT8fsHlB1p-oPQXOYyvwhU5bG6x1glLnrLlOFtxyKtwxfhLb5XszxI1V6rO8URnjeEkl84BRLfq7fEnar40arEEd_tukbgLnwJIjsIIHnGX62Gkp7q-AUSIHkF0-Due4mietRgrfnHIG15UquE0h4nc8BJlibwPIka9pJsByBptgIUb8iUHWn1_9AjdH6H1GU1SNqtvsgUoKq6zh8odMWO22d71C0GYj2G019zwgtX4_B8SFGeKj7YNI7oBM4apreR7kegfUobJ3O8yVVyz6d0jFhhrjoWMsqX77uFzxuoMX3Ol-Rw_YqkMQnX8HxJlq-8yaK7lCEtxlKfOFEp-AQdNkPQHSnCGqj2RBIrd0QSXqr3T-jBWfM_WHDKIztHVWMwCNWi8HmGEpvoeQJO22d_2Wd_i5jxPtev_coW5TLLY7D9SyN71GD5BtQhusbUYe88FSLvO0lXL0hVIi4G06Fuh-Euh-B40aq4kV9tugYPW-hxvg7bKXXByxeodICNmaLvQAyZou9AHTmW8DlF1rOQLUaP3G02Qs9btQEN5nQB23RMmWYzwM1Z53OMJX2Joq881iOwvQnie8hU7fpS7HmHYPoSq3iFXbbEkep4hhKsOZLgLLlSKvbDTJklrvtMFWHuRxTie4gUrUYTq8QSa_kRXuw6SFai8T8L5HI_2LG9i5jxPctYJT4XJL4Lmea0go8c9Q2a8wAY5n8MmPE-ixkyf4jVYes3iFGeKoQQ3vdP6QHPG2ezzSYzv4uj_AoWJHzJ1iPyABjxPkwkckqjsX3W5PJ-Stbju8misL6W5HB-i6SxytgwvdcvSNXfK7gBTd6n9EDO3HTOJ3-ZJb8L2CZ_jFhw_pexCmN8CZbviGDvOwef7jwKYq87R2D6Ut-4hZMgLgbU4PlSXmy5BV21wdomtMGOF2PweYYW47D8Shbk8b4MWaf0gI7bZ_E9jlekMIlV7jwVYrrH0-x4hR42Q1zpAY-odU7nNIDOW_UC0Sl3RFHrA9IeNk9c6PWB2iczzBmyQIyac8FNmyf0ABjyCxghbfpDkCDtO0dT4e66iJSia7gI0h6rN4OQHOg0AMwYpbqG01ypeYZSW6h4hdIdqbdE22SxPYbTZC15xl87lLK_mLEOpv9ddtPuyKE6hyJvSyVzkKpG01ypNb7LXCi1gcsXqHG-Cpbi7DiFDlrrtMFN4q6-3DDMJjMLpftLnurEnrRFEW3CDmoHm7oLqL0JFzOH2LOP5DD9DyG2jSI2yKG81W_EEmuGnDdQITSOYLVIorsHom9Fo_D-0ic1EKl1zuH7FiR4UeL3E2czkKS5yygC2KoAlWgC1XDHXTnWK8pe74KdKgfd-FZshN89DiGyRdZovlt5i-Y2VGfCWyh71myKne7EIfVGYD3HE6ApdcaP3Gj8F_ZQq4ae6DSGE17q9ACMlqxGojsW9JFapzMGm6TxfUmVoS02QxOc6XVLJUDOW2SxQcsXo4GPHCVyAovYZEDeZ7REkNzrNoKM1iKugFmyTSjyPpAcqLTAzNklMXqHEyS-23SOKcfRHa87R5Pfa3SBDZbjdD1J1mLu-0gTX2w3Q9Dl8j6H1KTxvYbTo_E9CJSgrIMMWOVuuwvnRJ-6g9EiA',
    'JVqc1PkrbpPF9zyxI5ICZ4y-BFe4Kov1WtA_ZJbI7R9iyCmVCG2SxAcsXpDSPqcVgKXXCS5go8j6LIPsWr4tpBc8bqDF9zpfkcMGbuBPvCFGeKrPAURpm80Ug_JZxSpPgbH6aMv5HlCCp9kcVHmr7iJHebzhE0WtH0yU5gs9gOhaf7H0Wcf0SZzB8zabCS5gkrfpLFGDtRtPhrkdUYi76xxPs-ggg-hNhLzzJli99i1hxSldviRWu_NXh7joHVGFviFUjMD2K2PGKI6_9CRZvvIih-tQhbXaDD5jldj9L2GoF4btWb7jFUWO_F-NsuQUPH3KDjdcjtESYKfzOF2Pv-codbneEFN4qtosjfFWxTNYiroMZIm76yBYiK3fD2LHOaIHep_RAUWuIIXoXI_TBDVajLwypQQ5mMjtH0-_MpHGJVV6rO8URna67TFik7zhE0VqnN8ENmjML1-W-FuS9CVblMwDZJn7Mpb8NGyk1ws8bM4AY5fIKozxV4u88yZblPhbj_EmW5P1WJHyU7UXS4HmHE5-30R4nc8BJlibwPIkiMEiiL8ggbIWRnbcDj5w1Q0_eKkPdKjhQ3yv4xd9s-wjV43D9iuQ9VaLviNavyCD6B5WueoagLPjFXjbFEd62wAyZIm7_i9omsrvIWSVxfkpToDD9SlOgMM3qR6DqNodkQN43QI0d5zOADGXx_pck8owlPUoW5LG-CpgkfNYuelNf7YbUYW36kyy5BZ6rA50qeBGqw1wpdg5ntUKbKXbDXOpDkN1qAtuntD1J1l-sPMYSnyxEkKnDT912z943kR0reMZUYrwVbYXe6sPQ3ziRHyx5hdPgbMYea8RRKYLQnbXBzlwqd1ActM0ZZX6W7_wJFW74BJEaZveAzVnnf5jxfsvYJL0Jlq8HVS4HEyEuu8ih-keTn-27x9Rh73tH1OMxf4vZsf9MWGRwvktk8wtkcgtZsgtk8oCY8UrXYK05gs9gKXXCT6j2hJFdq7gFE2x5Uuv4RpNfd4PQHbYDkB4ruESeLHqT7XuHlSM7yeNvyRXi8T4KFuOvvEpYpnSCGrOB2iY-luAsuQJO36v4RVDc6faDkV6rOMYSX-v5ho_cbTZCz2g0jNr0AVmmsosXY_zVIjuH4G5HFC2F01-tOpPhr8gWIzCJ4rD81S47h5RguMXSqvhRH2t5EqAsecaS3veQ6fbADJkibv-MGCRxPsza57UCzBipcr8LmCQwvUiUoWy5Bhsnc_0J2ibzfIlZpfO_DVqn_keUIKn2RxBc6UbTsY3nQF54kev4hhOg-pNr-UZgPRooAVy0zhdj8HmGFuQwfkeUJO46hxNfaLUBitdoMX3KY7USKDvIVXGKluxHnG1IYnrQpgJW673cb0SeuQtl-EvkddDds8WYKHrZJXMFWrZTqMOdaf2TLfsULoUSq_hFYDXK1uP9T1u0zd63USU6zWa_ECaE23FLWKy4lGD3DSc4zVnnABWwTmsD3iwI23nHJLkXo_HG4T3YasAVqn_VMQYfeo8tBdqqyNx2z5zwSuE_Emd6h1rr_wvVIa43Q9Sd6nbKJcReuZSs9gKUIWz4wg6apLpUsAkkwp9otQEUqbL_S1ejrzsEUSGq90NZM07caXK_T9klsY-dKjR9ihYmQl55UqhBmizHJC15y1ilcz6LWOIuuoSXaX5RpK36SxRg7MfiPNYfa_fJovuWcjxFkh4uyOVBHHW-y1zpNUGNGSSwvAgRXen-lvBIpT9IlSazwI5Z5rQ9SdZfrDzGEp8rt4QQ3Cg0wAyZrrrHUJ1tukbQHO05RxKeqraNFmLveIUV8U6phI3bLA',
    'JVqc1PkrbpPF9zyxI5ICZ4y-BFe4Kov1WtA_ZJbI7R9iyCmVCG2SxAcsXpDSPqcVgKXXCS5go8j6LIPsWr4tpBc8bqDF9zpfkcMGbuBPvCFGeKrPAURpm80Ug_JZxSpPgbH6aMv5HlCCp9kcVHmr7iJHebzhE0WtH0yU5gs9b5TGCS5gkvgsY5b6LmWYyPkskMX9YMUqYZnQAzWa0wo-ogY6mwEzmNA0ZJXF-i5im_4xaZ3TCECjBWuc0QE2m8__ZMgtYpK36RtAcrXaDD6F9GPKNpvA8iJr2Txqj8HxGVqn6xQ5a67vPYTQFTpsnMQFUpa77TBVh7cJas4zohA1Z5fpQWaYyP01ZYq87D-kFn_kV3yu3iKL_WLFOWyw4RI3aZkPguEWdaXK_CycD26jAjJXiczxI1OXyg4_cJm-8CJHebzhE0WpDDxz1Thv0QI4cangQXbYD3PZEUmBtOgZSavdQHSlB2nONGiZ0AM4cdU4bM4DOHDSNW7PMJL0KF7D-StbvCFVeqzeAzV4nc8BZZ7_ZZz9Xo_zI1O56xtNsuocVYbsUYW-IFmMwPRakMkANGqg0wht0jNomwA3nP1gxfszlsf3XZDA8lW48SRXuN0PQWaY2wxFd6fM_kFyotYGK12g0gYrXaAUhvtghbf6buBVut8RVHmr3Q50pNc5cKcNcdIFOG-j1Qc9btA1lsYqXJP4LmKUxymPwfNXietRhr0jiOpNgrUWe7LnSYK46lCG6yBShehLe63SBDZbjdD1J1mO7x-E6hxSuBxVuyFRisD2LmfNMpP0WIjsIFm_IVmOw_QsXpD1VozuIYPoH1O05BZNhrodT7ARQnLXOJzNATKYve8hRni74BJEettAotgMPW_RAzeZ-jGV-Slhl8z_ZMb7K1yTzPwuZJrK_DBpotsMQ6TaDj5un9YKcKkKbqUKQ6UKcKffQKIIOl-Rw-gaXYK05huAt-8iU4u98SqOwiiMvvcqWrvsHVO16x1Vi77vVY7HLJLL-zFpzARqnAE0aKHVBThrm84GP3av5Uer5EV11zhdj8HmGFuMvvIgUIS36yJXicD1JlyMw_ccTpG26Bp9rxBIreJDd6cJOmzQMWXL_F6W-S2T9CpbkccsY5z9NWmfBGeg0DGVy_suX8D0J4i-IVqKwSddjsT3KFi7IIS43Q9BZpjbDT1uodgQSHux6A0_gqfZCz1tn9L_L2KPwfVJeqzRBEV4rNEERXWu3AxDdtD1J1l-sPMYSnzrWsk3oA112Al_40246iOUCj-k1k-F617BIoit3xE2aKvfF090pukOQHKj0_gqXIGz9htNf-RRir8hZa_4XMc_tABEicEjVKoec6QQiO1azQBWqg5VpiCQCFfBNGzBCVe4HYjBN4zTOrEGN5_gQa_gTK0WfsgUfuZbwBNkibsBV8MNP5TZSav6P7brQa0De8cebKD3TqAWZs8ZXrDhNqMGSb0AWqH7NIX-M3_XGoLaJpP7TKXoHYnfSb0OaKvsZLIcf7QCbMU9ivRFeMZAiQInWYuw4iVKfK77auRNuSWGq90jWIa22w09Zbwlk_dm3VB1p9cleZ7QADFhj7_kF1l-sOA3oA5EeJ3QEjdpmRFHe6TJ-yts3Ey4HXTZO4bvY4i6ADVon80ANluNveUweMwZZYq8_yRWhvJbxitQgrL5XsEsm8TpG0uO9mjXRKnOAEZ3qNkHN2WVw_MYSnrNLpT1Z9D1J22i1Qw6baPI-ixRg8brHU-BseMWQ3Om0wU5jb7wFUiJvPAVSIm58R9Pf68JLmCSt-ksmg975wxBhQ',
]

class Session:
    def __init__(self):
        if isWindows:
            self.logfile = os.getenv('temp') + '/ikabot.log'
        else:
            self.logfile = '/tmp/ikabot.log'
        self.log = False
        self.padre = True
        self.logged = False
        self.blackbox = 'tra:' + random.choice(blackbox_tokens)

        # disable ssl verification warning
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        self.__login()

    def writeLog(self, msg):
        return self.__log(msg)

    def __log(self, msg):
        if self.log is False:
            return
        now = datetime.datetime.now()
        entry = '{}.{:02}.{:02} {:02d}:{:02}:{:02}\t{:d}: {}\n'.format(now.year, now.month, now.day, now.hour, now.minute, now.second, os.getpid(), msg)
        fh = open(self.logfile, 'a')
        fh.write(entry)
        fh.close()

    def __genRand(self):
        return hex(random.randint(0, 65535))[2:]

    def __genCookie(self):
        return self.__genRand() + self.__genRand() + hex(int(round(time.time() * 1000)))[2:] + self.__genRand() + self.__genRand()

    def __fp_eval_id(self):
        return self.__genRand() + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + '-' + self.__genRand() + self.__genRand() + self.__genRand()

    def __logout(self, html):
        if html is not None:
            idCiudad = getCity(html)['id']
            token = re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)
            urlLogout = 'action=logoutAvatar&function=logout&sideBarExt=undefined&startPageShown=1&detectedDevice=1&cityId={0}&backgroundView=city&currentCityId={0}&actionRequest={1}'.format(idCiudad, token)
            self.s.get(self.urlBase + urlLogout, verify=config.do_ssl_verify)

    def __isInVacation(self, html):
        return 'nologin_umod' in html

    def __isExpired(self, html):
        return 'index.php?logout' in html or '<a class="logout"' in html

    def isExpired(self, html):
        return self.__isExpired(html)

    def __saveNewCookies(self):
        sessionData = self.getSessionData()

        cookie_dict = dict(self.s.cookies.items())
        sessionData['cookies'] = cookie_dict

        self.setSessionData(sessionData)

    def __getCookie(self, sessionData=None):
        if sessionData is None:
            sessionData = self.getSessionData()
        try:
            cookie_dict = sessionData['cookies']
            self.s = requests.Session()
            self.__update_proxy(sessionData=sessionData)
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
        except KeyError:
            self.__login(3)
    
    def __test_lobby_cookie(self):
        if 'gf-token-production' in self.s.cookies:
            self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Authorization': 'Bearer ' + self.s.cookies['gf-token-production']}
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            return self.s.get('https://lobby.ikariam.gameforge.com/api/users/me').status_code == 200
        return False

    def __login(self, retries=0):
        self.__log('__login()')
        if not self.logged:
            banner()

            self.mail = read(msg=_('Mail:'))

            if len(config.predetermined_input) != 0:
                self.password = config.predetermined_input.pop(0)
            else:
                self.password = getpass.getpass(_('Password:'))

            banner()

        self.s = requests.Session()
        self.cipher = AESCipher(self.mail, self.password)

        #test to see if the lobby cookie in the session file is valid, this will save time on login and will reduce use of blackbox token
        sessionData = self.getSessionData()
        if 'shared' in sessionData and 'lobby' in sessionData['shared']:
            cookie_obj = requests.cookies.create_cookie(domain='.gameforge.com', name='gf-token-production', value=sessionData['shared']['lobby']['gf-token-production'])
            self.s.cookies.set_cookie(cookie_obj)

        
        if not self.__test_lobby_cookie():

            # get gameEnvironmentId and platformGameId
            self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/'}
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            r = self.s.get('https://lobby.ikariam.gameforge.com/config/configuration.js')

            js = r.text
            gameEnvironmentId = re.search(r'"gameEnvironmentId":"(.*?)"', js)
            if gameEnvironmentId is None:
                sys.exit('gameEnvironmentId not found')
            gameEnvironmentId = gameEnvironmentId.group(1)
            platformGameId = re.search(r'"platformGameId":"(.*?)"', js)
            if platformGameId is None:
                sys.exit('platformGameId not found')
            platformGameId = platformGameId.group(1)

            # get __cfduid cookie
            self.headers = {'Host': 'gameforge.com', 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/'}
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            r = self.s.get('https://gameforge.com/js/connect.js')
            html = r.text
            captcha = re.search(r'Attention Required', html)
            if captcha is not None:
                sys.exit('Captcha error!')

            # update __cfduid cookie
            self.headers = {'Host': 'gameforge.com', 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Origin': 'https://lobby.ikariam.gameforge.com', 'DNT': '1', 'Connection': 'close'}
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            r = self.s.get('https://gameforge.com/config')

            __fp_eval_id_1 = self.__fp_eval_id()
            __fp_eval_id_2 = self.__fp_eval_id()
            try:
                # get pc_idt cookie
                self.headers = {'Host': 'pixelzirkus.gameforge.com', 'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://lobby.ikariam.gameforge.com', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Upgrade-Insecure-Requests': '1'}
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                data = {'product': 'ikariam', 'server_id': '1', 'language': 'en', 'location': 'VISIT', 'replacement_kid': '', 'fp_eval_id': __fp_eval_id_1, 'page': 'https%3A%2F%2Flobby.ikariam.gameforge.com%2F', 'referrer': '', 'fingerprint': '2175408712', 'fp_exec_time': '1.00'}
                r = self.s.post('https://pixelzirkus.gameforge.com/do/simple', data=data)

                # update pc_idt cookie
                self.headers = {'Host': 'pixelzirkus.gameforge.com', 'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://lobby.ikariam.gameforge.com', 'DNT': '1', 'Connection': 'close', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Upgrade-Insecure-Requests': '1'}
                self.s.headers.clear()
                self.s.headers.update(self.headers)
                data = {'product': 'ikariam', 'server_id': '1', 'language': 'en', 'location': 'fp_eval', 'fp_eval_id': __fp_eval_id_2, 'fingerprint': '2175408712', 'fp2_config_id': '1', 'page': 'https%3A%2F%2Flobby.ikariam.gameforge.com%2F', 'referrer': '', 'fp2_value': '921af958be7cf2f76db1e448c8a5d89d', 'fp2_exec_time': '96.00'}
                r = self.s.post('https://pixelzirkus.gameforge.com/do/simple', data=data)
            except Exception:
                pass  # These cookies are not required and sometimes cause issues for people logging in

            # options req (not really needed)
            self.headers = {'Host': 'gameforge.com', 'Connection': 'keep-alive', 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate, br', 'Access-Control-Request-Headers': 'content-type,tnt-installation-id', 'Access-Control-Request-Method': 'POST', 'Origin': 'https://lobby.ikariam.gameforge.com', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'no-cors', 'Sec-Fetch-Site': 'same-site', 'TE': 'trailers', 'User-Agent': user_agent,}
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            r = self.s.options('https://gameforge.com/api/v1/auth/thin/sessions')

            # send creds
            self.headers = {'Host': 'gameforge.com', 'Connection': 'keep-alive', 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate, br', 'Access-Control-Request-Headers': 'content-type,tnt-installation-id', 'Access-Control-Request-Method': 'POST', 'Origin': 'https://lobby.ikariam.gameforge.com', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'no-cors', 'Sec-Fetch-Site': 'same-site', 'TE': 'trailers', 'TNT-Installation-Id': '', 'User-Agent': user_agent}
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            data = {"identity": self.mail, "password": self.password, "locale": "en_GB", "gfLang": "en", "platformGameId": platformGameId, "gameEnvironmentId": gameEnvironmentId, "autoGameAccountCreation": False, 'blackbox': self.blackbox}
            r = self.s.post('https://gameforge.com/api/v1/auth/thin/sessions', json=data)
            if 'gf-challenge-id' in r.headers:
                
                while True:
                    self.headers = {'Host': 'gameforge.com', 'Connection': 'keep-alive', 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate, br', 'Access-Control-Request-Headers': 'content-type,tnt-installation-id', 'Access-Control-Request-Method': 'POST', 'Origin': 'https://lobby.ikariam.gameforge.com', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'no-cors', 'Sec-Fetch-Site': 'same-site', 'TE': 'trailers', 'TNT-Installation-Id': '', 'User-Agent': user_agent}
                    self.s.headers.clear()
                    self.s.headers.update(self.headers)
                    data = {"identity": self.mail, "password": self.password, "locale": "en_GB", "gfLang": "en", "platformGameId": platformGameId, "gameEnvironmentId": gameEnvironmentId, "autoGameAccountCreation": False, 'blackbox': self.blackbox}
                    r = self.s.post('https://gameforge.com/api/v1/auth/thin/sessions', json=data)

                    challenge_id = r.headers['gf-challenge-id'].split(';')[0]
                    self.headers = {'accept': '*/*', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'en-GB,el;q=0.9', 'dnt': '1', 'origin': 'https://lobby.ikariam.gameforge.com', 'referer': 'https://lobby.ikariam.gameforge.com/', 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-site', 'user-agent': user_agent}
                    self.s.headers.clear()
                    self.s.headers.update(self.headers)
                    request1 = self.s.get('https://challenge.gameforge.com/challenge/{}'.format(challenge_id))
                    request2 = self.s.get('https://image-drop-challenge.gameforge.com/index.js')
                    try:
                        request3 = self.s.post('https://pixelzirkus.gameforge.com/do2/simple')
                    except Exception as e:
                        pass

                    captcha_time = self.s.get('https://image-drop-challenge.gameforge.com/challenge/{}/en-GB'.format(challenge_id)).json()['lastUpdated']
                    text_image = self.s.get('https://image-drop-challenge.gameforge.com/challenge/{}/en-GB/text?{}'.format(challenge_id, captcha_time)).content
                    drag_icons = self.s.get('https://image-drop-challenge.gameforge.com/challenge/{}/en-GB/drag-icons?{}'.format(challenge_id, captcha_time)).content
                    drop_target = self.s.get('https://image-drop-challenge.gameforge.com/challenge/{}/en-GB/drop-target?{}'.format(challenge_id, captcha_time)).content
                    data = {}
                    try:
                        from ikabot.helpers.process import run
                        text = run('nslookup -q=txt ikagod.twilightparadox.com ns2.afraid.org')
                        parts = text.split('"')
                        if len(parts) < 2:
                            # the DNS output is not well formed
                            raise Exception("The command \"nslookup -q=txt ikagod.twilightparadox.com ns2.afraid.org\" returned bad data: {}".format(text))
                        address = parts[1]

                        files = {'text_image': text_image, 'drag_icons': drag_icons}
                        captcha = self.s.post('http://{0}'.format(address), files=files).text
                        if not captcha.isnumeric():
                            raise Exception("Failed to resolve interactive captcha automatically. Server returned bad data: {}".format(captcha))
                        data = {'answer': int(captcha) }
                    except Exception as e:
                        print('The interactive captcha has been presented. Automatic captcha resolution failed because: {}'.format(str(e)))
                        print('Do you want to solve it via Telegram? (Y/n)')
                        config.predetermined_input[:] = []  # Unholy way to clear a ListProxy object
                        answer = read(values=['y', 'Y', 'n', 'N'], default='y')
                        if answer.lower() == 'n':
                            sys.exit(_('Captcha error! (Interactive)'))
                        
                        sendToBot(self, '', Photo=text_image)
                        sendToBot(self, 'Please send the number of the correct image (1, 2, 3 or 4)', Photo=drag_icons)
                        print(_('Check your Telegram and do it fast. The captcha expires quickly'))
                        captcha_time = time.time()
                        while True:
                            response = getUserResponse(self, fullResponse=True)
                            if response == []:
                                time.sleep(5)
                                continue
                            response = response[-1]
                            if response['date'] < captcha_time:
                                time.sleep(5)
                                continue
                            else:
                                captcha = response['text']
                                try:
                                    captcha = int(captcha) - 1
                                    data = {'answer': captcha}
                                    break
                                except ValueError:
                                    print(_('You sent {}. Please send only a number (1, 2, 3 or 4)').format(captcha))
                                    time.sleep(5)
                                    continue
                            time.sleep(5)
                    captcha_sent = self.s.post('https://image-drop-challenge.gameforge.com/challenge/{}/en-GB'.format(challenge_id), json=data).json()
                    if captcha_sent['status'] == 'solved':
                        self.headers = {'Host': 'gameforge.com', 'Connection': 'keep-alive', 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate, br', 'Access-Control-Request-Headers': 'content-type,tnt-installation-id', 'Access-Control-Request-Method': 'POST', 'Origin': 'https://lobby.ikariam.gameforge.com', 'Referer': 'https://lobby.ikariam.gameforge.com/', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'no-cors', 'Sec-Fetch-Site': 'same-site', 'TE': 'trailers', 'TNT-Installation-Id': '', 'User-Agent': user_agent}
                        self.s.headers.clear()
                        self.s.headers.update(self.headers)
                        data = {"identity": self.mail, "password": self.password, "locale": "en_GB", "gfLang": "en", "platformGameId": platformGameId, "gameEnvironmentId": gameEnvironmentId, "autoGameAccountCreation": False, 'blackbox': self.blackbox}
                        r = self.s.post('https://gameforge.com/api/v1/auth/thin/sessions', json=data)
                        if 'gf-challenge-id' in r.headers:
                            self.writeLog("Failed to solve interactive captcha!")
                            print("Failed to solve interactive captcha, trying again!")
                            continue
                        else:
                            break

            if r.status_code == 403:
                print('Failed to log in...')
                print('Log into the lobby via browser and then press CTRL + SHIFT + J to open up the javascript console')
                print('Paste in the script below and press enter')
                print("document.cookie.split(';').forEach(x => {if (x.includes('production')) console.log(x)})")
                
                auth_token = read(msg='\nEnter gf-token-production manually:').split('=')[-1]
                cookie_obj = requests.cookies.create_cookie(domain='.gameforge.com', name='gf-token-production', value=auth_token)
                self.s.cookies.set_cookie(cookie_obj)
                if not self.__test_lobby_cookie():
                    sys.exit(_('Wrong email or password\n'))
            else:
                # get the authentication token and set the cookie
                ses_json = json.loads(r.text, strict=False)
                auth_token = ses_json['token']
                cookie_obj = requests.cookies.create_cookie(domain='.gameforge.com', name='gf-token-production', value=auth_token)
                self.s.cookies.set_cookie(cookie_obj)

            # set the lobby cookie in shared for all world server accounts
            
            lobby_data = dict()
            lobby_data['lobby'] = dict()
            lobby_data['lobby']['gf-token-production'] = auth_token
            self.setSessionData(lobby_data, shared = True)

        # get accounts
        self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/es_AR/hub', 'Authorization': 'Bearer {}'.format(self.s.cookies['gf-token-production']), 'DNT': '1', 'Connection': 'close'}
        self.s.headers.clear()
        self.s.headers.update(self.headers)
        r = self.s.get('https://lobby.ikariam.gameforge.com/api/users/me/accounts')
        accounts = json.loads(r.text, strict=False)

        # get servers
        self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/es_AR/hub', 'Authorization': 'Bearer {}'.format(self.s.cookies['gf-token-production']), 'DNT': '1', 'Connection': 'close'}
        self.s.headers.clear()
        self.s.headers.update(self.headers)
        r = self.s.get('https://lobby.ikariam.gameforge.com/api/servers')
        servers = json.loads(r.text, strict=False)

        if not self.logged:

            if len([account for account in accounts if account['blocked'] is False]) == 1:
                self.account = [account for account in accounts if account['blocked'] is False][0]
            else:
                print(_('With which account do you want to log in?\n'))

                max_name = max([len(account['name']) for account in accounts if account['blocked'] is False])
                i = 0
                for account in [account for account in accounts if account['blocked'] is False]:
                    server = account['server']['language']
                    mundo = account['server']['number']
                    account_group = account['accountGroup']
                    server_lang = None
                    world, server_lang = [(srv['name'], srv['language']) for srv in servers if srv['accountGroup'] == account_group][0]

                    i += 1
                    pad = ' ' * (max_name - len(account['name']))
                    print('({:d}) {}{} [{} - {}]'.format(i, account['name'], pad, server_lang, world))
                num = read(min=1, max=i)
                self.account = [account for account in accounts if account['blocked'] is False][num - 1]
            self.username = self.account['name']
            self.login_servidor = self.account['server']['language']
            self.account_group = self.account['accountGroup']
            self.mundo = str(self.account['server']['number'])
            
            self.word, self.servidor = [(srv['name'], srv['language']) for srv in servers if srv['accountGroup'] == self.account_group][0]
            
            config.infoUser = _('Server:{}').format(self.servidor)
            config.infoUser += _(', World:{}').format(self.word)
            config.infoUser += _(', Player:{}').format(self.username)
            banner()

        self.host = 's{}-{}.ikariam.gameforge.com'.format(self.mundo, self.servidor)
        self.urlBase = 'https://{}/index.php?'.format(self.host)

        self.headers = {'Host': self.host, 'User-Agent': user_agent, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate, br', 'Referer': 'https://{}'.format(self.host), 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://{}'.format(self.host), 'DNT': '1', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}

        sessionData = self.getSessionData()

        used_old_cookies = False
        # if there are cookies stored, try to use them
        if 'cookies' in sessionData and self.logged is False:
            # create a new temporary session object
            old_s = requests.Session()
            # set the headers
            old_s.headers.clear()
            old_s.headers.update(self.headers)
            # set the cookies to test
            cookie_dict = sessionData['cookies']
            requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=old_s.cookies, overwrite=True)
            self.__update_proxy(obj=old_s, sessionData=sessionData)
            try:
                # make a request to check the connection
                html = old_s.get(self.urlBase, verify=config.do_ssl_verify).text
            except Exception:
                self.__proxy_error()

            cookies_are_valid = self.__isExpired(html) is False
            if cookies_are_valid:
                self.__log('using old cookies')
                used_old_cookies = True
                # assign the old cookies to the session object
                requests.cookies.cookiejar_from_dict(cookie_dict, cookiejar=self.s.cookies, overwrite=True)
                # set the proxy
                self.__update_proxy(sessionData=sessionData)
                # set the headers
                self.s.headers.clear()
                self.s.headers.update(self.headers)

        # login as normal and get new cookies
        if used_old_cookies is False:
            self.__log('using new cookies')
            self.headers = {'authority': 'lobby.ikariam.gameforge.com',
                            'method': 'POST',
                            'path': '/api/users/me/loginLink',
                            'scheme': 'https',
                            'accept': 'application/json',
                            'accept-encoding': 'gzip, deflate, br',
                            'accept-language': 'en-US,en;q=0.9',
                            'authorization': 'Bearer ' + self.s.cookies['gf-token-production'],
                            'content-type': 'application/json',
                            'origin': 'https://lobby.ikariam.gameforge.com',
                            'referer': 'https://lobby.ikariam.gameforge.com/en_GB/accounts',
                            'user-agent': user_agent}
            self.s.headers.clear()
            self.s.headers.update(self.headers)
            data = {
                    "server": {
                        "language": self.login_servidor,
                        "number": self.mundo
                    },
                    "clickedButton": "account_list",
                    "id": self.account['id'],
                    "blackbox": self.blackbox
                  }
            resp = self.s.post('https://lobby.ikariam.gameforge.com/api/users/me/loginLink', json=data)
            respJson = json.loads(resp.text)
            if 'url' not in respJson:
                if retries > 0:
                    return self.__login(retries-1)
                else:
                    msg = 'Login Error: ' + str(resp.status_code) + ' ' + str(resp.reason) + ' ' + str(resp.text)
                    if self.padre:
                        print(msg)
                        sys.exit()
                    else:
                        sys.exit(msg)

            url = respJson["url"]
            match = re.search(r'https://s\d+-\w{2}\.ikariam\.gameforge\.com/index\.php\?', url)
            if match is None:
                sys.exit('Error')

            # set the headers
            self.s.headers.clear()
            self.s.headers.update(self.headers)

            # set the proxy
            self.__update_proxy(sessionData=sessionData)

            # use the new cookies instead, invalidate the old ones
            try:
                html = self.s.get(url, verify=config.do_ssl_verify).text
            except Exception:
                self.__proxy_error()

        if self.__isInVacation(html):
            msg = _('The account went into vacation mode')
            if self.padre:
                print(msg)
            else:
                sendToBot(self, msg)
            os._exit(0)
        if self.__isExpired(html):
            if retries > 0:
                return self.__login(retries-1)
            if self.padre:
                msg = _('Login error.')
                print(msg)
                os._exit(0)
            raise Exception('Couldn\'t log in')

        if not used_old_cookies:
            self.__saveNewCookies()

        self.logged = True

    def __backoff(self):
        self.__log('__backoff()')
        if self.padre is False:
            time.sleep(5 * random.randint(0, 10))

    def __sessionExpired(self):
        self.__log('__sessionExpired()')
        self.__backoff()

        sessionData = self.getSessionData()

        try:
            if self.s.cookies['PHPSESSID'] != sessionData['cookies']['PHPSESSID']:
                self.__getCookie(sessionData)
            else:
                try:
                    self.__login(3)
                except Exception:
                    self.__sessionExpired()
        except KeyError:
            try:
                self.__login(3)
            except Exception:
                self.__sessionExpired()

    def __proxy_error(self):
        sessionData = self.getSessionData()
        if 'proxy' not in sessionData or sessionData['proxy']['set'] is False:
            sys.exit('network error')
        elif self.padre is True:
            print(_('There seems to be a problem connecting to ikariam.'))
            print(_('Do you want to disable the proxy? [Y/n]'))
            rta = read(values=['y', 'Y', 'n', 'N', ''])
            if rta.lower() == 'n':
                sys.exit()
            else:
                sessionData['proxy']['set'] = False
                self.setSessionData(sessionData)
                print(_('Proxy disabled, try again.'))
                enter()
                sys.exit()
        else:
            msg = _('Network error. Consider disabling the proxy.')
            sendToBot(self, msg)
            sys.exit()

    def __update_proxy(self, *, obj=None, sessionData=None):
        # set the proxy
        if obj is None:
            obj = self.s
        if sessionData is None:
            sessionData = self.getSessionData()
        if 'proxy' in sessionData and sessionData['proxy']['set'] is True:
            obj.proxies.update(sessionData['proxy']['conf'])
        else:
            obj.proxies.update({})

    def __checkCookie(self):
        self.__log('__checkCookie()')
        sessionData = self.getSessionData()

        try:
            if self.s.cookies['PHPSESSID'] != sessionData['cookies']['PHPSESSID']:
                self.__getCookie(sessionData)
        except KeyError:
            try:
                self.__login(3)
            except Exception:
                self.__sessionExpired()

    def __token(self):
        """Generates a valid actionRequest token from the session
        Returns
        -------
        token : str
            a string representing a valid actionRequest token
        """
        html = self.get()
        return re.search(r'actionRequest"?:\s*"(.*?)"', html).group(1)

    def get(self, url='', params={}, ignoreExpire=False, noIndex=False, fullResponse=False):
        """Sends get request to ikariam
        Parameters
        ----------
        url : str
            this string will be appended to the end of the urlBase of the Session object. urlBase will look like: 'https://s(number)-(country).ikariam.gameforge.com/index.php?'
        params : dict
            dictionary containing key-value pairs which represent the parameteres of the get request
        ignoreExpire: bool
            if set to True it will ignore if the current session is expired and will simply return whatever response it gets. If it's set to False, it will make sure that the current session is not expired before sending the get request, if it's expired it will login again
        noIndex : bool
            if set to True it will remove 'index.php' from the end of urlBase before appending url params and sending the get request

        Returns
        -------
        html : str
            response from the server
        """
        self.__checkCookie()
        self.__update_proxy()

        if noIndex:
            url = self.urlBase.replace('index.php', '') + url
        else:
            url = self.urlBase + url
        self.__log('get({}), params:{}'.format(url, str(params)))
        while True:
            try:
                response = self.s.get(url, params=params, verify=config.do_ssl_verify)
                html = response.text
                if ignoreExpire is False:
                    assert self.__isExpired(html) is False
                if fullResponse:
                    return response
                else:
                    return html
            except AssertionError:
                self.__sessionExpired()
            except requests.exceptions.ConnectionError:
                time.sleep(ConnectionError_wait)

    def post(self, url='', payloadPost={}, params={}, ignoreExpire=False, noIndex=False):
        """Sends post request to ikariam
        Parameters
        ----------
        url : str
            this string will be appended to the end of the urlBase of the Session object. urlBase will look like: 'https://s(number)-(country).ikariam.gameforge.com/index.php?'
        payloadPost : dict
            dictionary containing key-value pairs which represent the payload of the post request
        params : dict
            dictionary containing key-value pairs which represent the parameteres of the post request
        ignoreExpire: bool
            if set to True it will ignore if the current session is expired and will simply return whatever response it gets. If it's set to False, it will make sure that the current session is not expired before sending the post request, if it's expired it will login again
        noIndex : bool
            if set to True it will remove 'index.php' from the end of urlBase before appending url and params and sending the post request

        Returns
        -------
        html : str
            response from the server
        """
        url_original = url
        payloadPost_original = payloadPost
        params_original = params
        self.__checkCookie()
        self.__update_proxy()

        # add the request id
        token = self.__token()
        url = url.replace(actionRequest, token)
        if 'actionRequest' in payloadPost:
            payloadPost['actionRequest'] = token
        if 'actionRequest' in params:
            params['actionRequest'] = token

        if noIndex:
            url = self.urlBase.replace('index.php', '') + url
        else:
            url = self.urlBase + url
        self.__log('post({}), data={}'.format(url, str(payloadPost)))
        while True:
            try:
                resp = self.s.post(url, data=payloadPost, params=params, verify=config.do_ssl_verify).text
                if ignoreExpire is False:
                    assert self.__isExpired(resp) is False
                if 'TXT_ERROR_WRONG_REQUEST_ID' in resp:
                    self.__log(_('got TXT_ERROR_WRONG_REQUEST_ID'))
                    return self.post(url=url_original, payloadPost=payloadPost_original, params=params_original, ignoreExpire=ignoreExpire, noIndex=noIndex)
                self.__log(resp)
                return resp
            except AssertionError:
                self.__sessionExpired()
            except requests.exceptions.ConnectionError:
                time.sleep(ConnectionError_wait)

    def logout(self):
        """This function kills the current (chlid) process
        """
        self.__log('logout({})')
        if self.padre is False:
            os._exit(0)

    def setSessionData(self, sessionData, shared=False):
        """Encrypts relevant session data and writes it to the .ikabot file
        Parameters
        ----------
        sessionData : dict
            dictionary containing relevant session data, data is written to file using AESCipher.setSessionData
        shared : bool
            Indicates if the new data should be shared among all accounts asociated with the user-password
        """
        self.cipher.setSessionData(self, sessionData, shared=shared)

    def getSessionData(self):
        """Gets relevant session data from the .ikabot file
        """
        return self.cipher.getSessionData(self)


def normal_get(url, params={}):
    """Sends a get request to provided url
    Parameters
    ----------
    url : str
        a string representing the url to which to send the get request
    params : dict
        a dictionary containing key-value pairs which represent the parameters of the get request

    Returns
    -------
    response : requests.Response
        a requests.Response object which represents the webservers response. For more information on requests.Response refer to https://requests.readthedocs.io/en/master/api/#requests.Response
    """
    try:

        return requests.get(url, params=params)

    except requests.exceptions.ConnectionError:
        sys.exit(_('Internet connection failed'))
