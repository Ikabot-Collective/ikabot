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


class Session:
    def __init__(self):
        if isWindows:
            self.logfile = os.getenv('temp') + '/ikabot.log'
        else:
            self.logfile = '/tmp/ikabot.log'
        self.log = False
        self.padre = True
        self.logged = False
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

        #set blackbox
        blackbox_tokens = [
            'JVqc1PkrbpPF9zyxI5ICZ4y-BFe4Kov1WtA_ZJbI7R9iyCmVCG2SxAcsXpDSPqcVgKXXCS5go8j6LIPsWr4tpBc8bqDF9zpfkcMIbNM4XY_B5hhbgLLkK5oJcNxBZpjIEX_iEDVnmb7wM2uQwgU5XpDT-CpcwS9csQQpW54DcZbIC3PlCjxuk8UILV-R9ytilfktZJfH-CuPxPxfxClgmM8CNJnSCT2hBTmaADKXzzNjlMT5LWGa_TBonNIHP6IEapvQADWazv5jxyxhkbboGj9xtNkLPYTzYsk1mr_xIWrYO2mOwPAYWabqEzhqre48g88UOWubwwRRlbrsL1SGtghpzTKhDzRmlugfRHam2Q8_ZJbGGX7wWb4xVoi4_GXXPJ8TRoq77BFDc-lcu_BPf6TWBnbpSH3cDDFjpsv9LXGk6BlLdJnL_SJUl7zuIITnF06wE0qs3RNMhLscUbPqTrTsJFyPw_QkhrgbT4DiRKkPQ3Sr3hNMsBNHqd4TS60QSaoLbc8DOZ7UBjaX_DBVh7neEFN4qtxAedpAd9g5as7-LpTG9iiNxfcwYccsYJn7NGebzzVrpNsPRXuu40itDkN22xJ32Dug1g5xotI4a5vNMJPM_zKTuOocQXO25yBSgqfZHE19seEGOHut4QY4e-9h1jtgktVJuzCVuuwvVIa46U9_shRLguhMreATSn6w4hhJqxBxoQU3btMJPW-iBGqczjJkxixhmP5jxShdkPFWjcIkXZPFK2HG-y1gwyZWiK3fETZoq9ACNGnK-l_F9y2T9zCW_Cxlm9EJQqgNbs8zY8f7NJr8NGmezwc5a9AxZ8n8XsP6Lo-_8Shhlfgqi-wdTbITd6jcDXOYyvwhU5a77R9Vtht9s-cYSqzeEnTVDHDUBDxyp9o_odYGN26n1wk_daXXC0R9tucef7XpGUl6seVLhOVJgOUegOVLgrobfeMVOmyew_U4XY_B9luSyv0uZpjMBWmdA2eZ0gU1lsf4LpDG-DBmmcowaaIHbabWDESn30V33A9DfLDgE0Z2qeEaUYrAIoa_IFCyEzhqnMHzNmeZzfsrX5LG_TJkm9ABN2ee0vcpbJHD9ViK6yOIvR5SguQVR6sMQKbXOXHUCG7PBTZsogc-d9gQRHrfQnurDHCm1gk6m88CY5n8NWWcAjhpn9IDM5b7X5O46hxBc7bsI1mOxfUqY5S56y5ThbfpGUt-q9sOO2yg9CZWe67vIVp_svMjU4G27SaApdcJLmCjyPosngU8teljnAJv0Tyw6EuA7ljJNGnSQbIaToT2G01_pNYZT3-12gxPdKbYCTlekMLnGVyBs-UzecseZ74yqfc_pxRp1RuCyw9-7VC6EFawGYH1T6P1N4LHLpfjFmSb8Ee7L5PWCoDRJF3OHU7CDmPRF4ntH4_XMZ3eRpbpMqcIdeFWoAxAecIsXJTmPn_0WrHmOI_kS70PQY_DDVHAK3TKOonhKJwSaNVMhNcKZMgrpOouh_Flm-tk1COFyAmBzzmc0B9jrN0rpfIndsotp8z-MFWHyu8hU6APifJeyitQgsj9K1uAsuIKYco4nAuC9RpMfMoeQ3Wl1gY0ZIm8_iNVhdxFs-kdQnW33A4-tuwgRXi63xFBsylOgcLzI1yKuuMIOmqxFnnkU3iq8CJSg7PjFER1msz8QqsdguhXz_QmbJ3O_ixcgbPlCjx_pNYIOmqcz_wsX4y98UV3qc4BQnOozQBBcaHP_y9fud4QQmeZ3Eq_K5e88TU',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BEarF37wUbUaP3GjyPo9owRw40htn-IHOWutGYLwW4Cy5Ak7fqPVB17HNZkIf_IXSXug0hU6bJ7jR64TOGqcwfM2W42_BnXkS7ccQXOj7Fq96xBCdJnLDkZrneAUOWuu0wU3nAo3jN8ENnneTHGj5k7A5RdJbqDjCDps0gY9cNQIP3Ki0wZqn9c6nwQ7c6rdD3St5Bh84BR12w1yqg4-b5_UCDx12AtDd63iGn3fRXar2xB1qdk-ogc8bJHD9RpMj7TmGF_OPaQQdZrM_EWzFkRpm8vzNIHF7hNFiMkXXqrvFEZ2nt8scJXHCi9hkeNEqA186g9BccP6H1GBtOoaP3Gh9FnLNJkMMWOT10CyF3ruIWWWx-weTsQ3lssqWn-x4VHEI1i35ww-gabYCEx_w_QmT3Sm2P0vcpfJ-1_C8imL7iWHuO4nX5b3LI7FKY_H_zdqns__YZP2Klu9H4TqHk-Gue4ni-4ihLnuJojrJIXmSKreFHmv4RFy1wswYpS56y5ThbcbVLUbUrMURanZCW-h0QNooNILPKIHO3TWD0J2qhBGf7bqIFaJviOI6R5Rtu1SsxZ7selMfa0TRnaoC26n2g1uk8X3HE6RwvstXYK09yhYjLzhE1aIvOETVso8sRY7bbAklgtwlccKL2GTxCpaje8mXcMniLvuJVmLvfMkhutMfOASSa7kGEp930V3qQ0_oQc8c9k-oAM4a8wxaJ3_OG6gBjyh1gg7ngExY4i67BFDhqvdD0Sl1Tqg0ghu0gtx1wdAdqzkHYPoSaoOPqLWD3XXD0R5quIURqsMQqTXOZ7VCWqazAM8cNMFZsf4KI3uUoO36E5zpdf8LnGWyPowkfZYjsLzJYe57U-w50uv3xdNgrUafLHhEkmCsuQaUICy5h9YkcL5WpDE9CRVjMAmX8AkW8D5W8AmXZX2WL7wFUd5ntATOGqc0TZtpdgJQXOn4ER43kJ0reAQcaLTCWuh0wtBdKULRH3iSIGx5x-CuiBSt-oeV4u77iFRhLz1LGWb_WGa-yuN7hNFd5zOEUJ0qNYGOm2h2A0_dqvcEkJ5rdIER2ye0DNlxv5jmPktXb_wIobnG4GyFEyv40mq4BFHfeIZUrPrH1W6HVaG50uBseQVdqrdPnTXEEB33RNEeq3eDnHWOm6TxfccTpHH_jRpoNAFPm-UxgkuYJLE9CZZhrbpFkd7zwExVonK_DVajc7-LlyRyAFbgLLkCTt-o9UHeeAXkMQ-d91KrBeLwyZbyTOkD0StHI31KV_R9ihaf7H0KlqQtecqT4Gz5BQ5a53C9DdcjsAOVKb5QpkNhNIagu9EsPZdpupZyCuV6zGL9FzQKn7QEl2iCXK-8T92yyKWCm6x5Vus_zip-Cmd6T6s8mTI-mqyDHi5IXHEDYLjULwxe-cbVJ0HN2_BGVrPNYzBE2q_JpjqHGqe6CybBk-lFWS8A3ftQ7AnX7LlP6MGf8UJYsxAdsY_r_5go-RcqhR3q_o-h7gGgM0CUaUIgqfZCzBipcr8LnvqZM05pQYrXaPYBjZbjb3lPKUTd-Zd0PUnV6X5HlCAseEPP2SX2f4wYLcgjsT4HVCSt-kZkcf7IFOVuuwcjgQpXJ3O_jdllb7jFUWM8VS_LlOFy_0tXo6-7x9QdafXHYb4XcMyqs8BR3ip2Qc3XI7A5Rdaf7HjFUV3qtcHOmeYzCBShKncHU6DqNscTHyq2go6lLnrHUJ0tyWaBnKXzBA',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BFTGJ44DaI2_8RZIi_FSvjGWu-0wVYe5-2fQPqnOADJXiczxI1WsFYPnVs1AZZfJ7iBjiLrsMZX8YYa46g9BhKnbDVTDMpkFao_B8TqoCzlekMLnGVyUuesuYoe5_CFThepYhdotUoTHLJq_8TScDjNll7zuMVaIuiBUi74iVo3A8CFUuO0liO1SicH4K13C-zJmyi5iwylbwPhcjL3tIlaKwyZZkcX7MGjLLZPE-Slew_cnjPBVirrfEUNomt0CNGatHIvyXsPoGkqTAWSSt-kZQYLPEzxhk9YXZaz4PWKUxOwter7jFVh9r98xkvZbyjhdj78RSG2fzwI4aI2_70KnGYLnWn-x4SWOAGXIPG-z5BU6bJwSheQZeKjN_y-fEnGmBTVajM_0JlaazRFCdJ3C9CZLfcDlF0mtEEB32Txz1QY8da3kRXrcE3fdFU2FuOwdTa_hRHipC23SOGyd1Ac8ddk8cNIHPHTWOXLTNJb4LGLH_S9fwCVZfrDiBzl8odMFaaIDaaABYpP3J1e97x9Rtu4gWYrwVYnCJF2QxPhelM0EOG6k1wxx1jdsnwQ7oAFkyf83msv7YZTE9lm89ShbvOETRWqc3xBJe6vQAkV2ptoKL2Gk1govYaQYiv9kibv-cuRZvuMVWH2v4RJ4qNs9dKsRddYJPHOn2QtBctQ5msouYJf8MmaYyy2Txfdbje9VisEnjO5Rhrkaf7brTYa87lSK7yRWiexPf7HWCDpfkdT5K12S8yOI7iBWvCBZvyVVjsT6MmvRNpf4XIzwJF3DJV2Sx_gwYpT5WpDyJYfsI1e46BpRir4hU7QVRnbbPKDRBTacwfMlSny_5BZIft9EptwQQXPVBzud_jWZ_S1lm9ADaMr_L2CX0AAyaJ7OADRtpt8QR6jeEkJyo9oOdK0OcqkOR6kOdKvjRKYMPmOVx-weYYa46h-Eu_MmV4_B9S6SxiyQwvsuXr_wIVe57yFZj8LzWZLLMJbP_zVt0AhuoAU4bKXZCTxvn9IKQ3qz6Uuv6El52zxhk8XqHF-QwvYkVIi77yZbjcT5KmCQx_sgUpW67B6BsxRMseZHe6sNPnDUNWnPAGKa_TGX-C5flcswZ6ABOW2jCGuk1DWZz_8yY8T4K4zCJV6OxSthksj7LFy_JIi84RNFapzfFUyCt-4eU4y94hRXfK7gEkJ0p9QEN2SVyR1Pf6TXGEqDqNscTHyq3xZPqc4AMleJzPEjVccuZd4SjMUrmPpl2RF0qReB8l2S-2rbQ3etH0R2qM3_Qnio3gM1eJ3PATJih7nrEEKFqtwOXKL0R5DnW9IgaNA9kv5Eq_Q4pxZ54zl_2UKqHnjMHmCr8FfADD-NxBlw5Fi8_zOp-k2G90Z36zeM-kCyFki4AFrGB2-_ElvQMZ4Kf8k1aaLrVYW9D2eoHYPaD2G4DXTmOGq47DZ66VSd82OyClHFO5H-da0AM43xVM0TV7AajsQUjf1MrvEyqvhixflIjNUGVM4bUJ_zVtD1J1l-sPMYSnzJOLIbh_NUeavxJlSEqdsLM4rzYcU0qx5DdaXzR2yezv8vXY2y5SdMfq4FbtwSRmue4AU3Z98VSW6h4wg6atxSd6rrHEyFs-MMMWOT2j-iDXyh0xlLe6zcDD1tnsP1JWvURqsRgPgdT5XG9ydVharcDjNlqM3_MWOTxfglVYi15hpuoNL3Kmuc0fYpaprK-ChYiOIHOWuQwgVz6FTA5Rpe',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BEarF37wUbUaP3GjyPo9owRw40htn-IHOWutGYLwW4Cy5Ak7fqPVB17HNZkIf_IXSXug0hU6bJ7jR64TOGqcwfM2W42_BnXkS7ccQXOj7Fq96xBCdJnLDkZrneAUOWuu0wU3nAo3jN8ENnneTHGj5k7A5RdJbqDjCDps0gY9cNQIP3Ki0wZqn9c6nwQ7c6rdD3St5Bh84BR12w1yqg4-b5_UCDx12AtDd63iGn3fRXar2xB1qdk-ogc8bJHD9RpMj7TmGF_OPaQQdZrM_EWzFkRpm8vzNIHF7hNFiMkXXqrvFEZ2nt8scJXHCi9hkeNEqA186g9BccP7IFKCte4eQ3Wl-F3POJ0QNWeX20S2G37yJWmay_AiUsg7ms8uXoO15VXIJ1y76xBCharcDFCDx_gqU3iq3AEzdpvN_2PG9i2P8imLvPIrY5r7MJLJLZPLAztuotMDZZf6Ll_BI4juIlOKvfIrj_ImiL3yKozvKInqTK7iGH2z5RV22w80Zpi97zJXibsfWLkfVrcYSa3dDXOl1QdspNYPQKYLP3jaE0Z6rhRKg7ruJFqNwieM7SJVuvFWtxp_te1QgbEXSnqsD3Kr3hFyl8n7IFKVxv8xYYa4-yxckMDlF1qMwOUXWs5AtRo_cbQomg90mcsOM2WXyC5ekfMqYccrjL_yKV2Pwfcoiu9QgOQWTbLoHE6B40l7rRFDpQtAd91CpAc8b9A1bKEDPHKkCkCl2gw_ogU1Z4y-8BVHiq_hE0ip2T6k1gxy1g912wtEerDoIYfsTa4SQqbaE3nbE0h9ruYYSq8QRqjbPaLZDW6e0AdAdNcJasv8LJHyVoe77FJ3qdsAMnWazP40lfpcksb3KYu98VO060-z4xtRhrkegLXlFk2GtugeVIS26iNclcb9XpTI-ChZkMQqY8QoX8T9X8QqYZn6XML0GUt9otQXPG6g1TpxqdwNRXer5Eh84kZ4seQUdabXDW-l1w9FeKkPSIHmTIW16yOGviRWu-4iW4-_8iVViMD5MGmfAWWe_y-R8hdJe6DSFUZ4rNoKPnGl3BFDeq_gFkZ9sdYIS3Ci1DdpygJnnP0xYcP0JorrH4W2GFCz502u5BVLgeYdVrfvI1m-IVqK60-FtegZeq7hQnjbFER74RdIfrHiEnXaPnKXyfsgUpXLAjhtpNQJQnOYyg0yZJbI-CpdirrtGkt_0wU1Wo3OADlekdICMmCVzAVfhLboDT-Cp9kLfeQblMhCe-FOsBuPxypfzTeoE0ixIJH5LWPV-ixeg7X4Ll6UuesuU4W36Bg9b6HG-DtgksQSWKr9Rp0RiNYehvNItPphqu5dzC-Z7zWP-GDULoLUFmGmDXbC9UN6zyaaDnK16V-wAzyt_C2h7UKw9mjM_m62EHy9JXXIEYbnVMA1f-sfWKELO3PFHV7TOZDFF27DKpzuIG6i7DCfClOpGWjAB3vxR7QrY7bpQ6cKg8kNZtBEespDswJkp-hgrhh7r_5Ci7wKhNEGVakMhqvdDzRmqc4AMn_uaNE9qQovYafcCjpfkcHpQKkXe-ph1PkrW6n9IlSEteUTQ2ib3QI0ZLskksj8IVSWu-0dlcv_JFeZvvAgkggtYKHSAjtpmcLnGUmQ9VjDMleJzwExYpLC8yNUeavbIYr8Ycc2rtMFS3yt3Qs7YJLE6Rteg7XnGUl7rtsLPmuc0CRWiK3gIVKHrN8gUICu3g4-mL3vIUZ4uymeCnab0BQ',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BEarF37wUbUaP3GjyPo9owRw40htn-IHOWutGYLwW4Cy5Ak7fqPVB1O8Kp8XPG6gxfc6X5HDCXLkSa8elrvtH0R2ud4QQon4Z846n8T2Jm_dQG6TxfccTpHJ7iBjl7zuMVaIuh-Nug9ih7n8Yc_0JmnRQ2iazPEjZou971WJwPNXi8L1JVaJ7SJavSKHvvYtYJL3MGeb_2OX-F6Q9S2RwfIiV4u_-FuOxvowZZ0AYsj5Ll6T-CxcwSWKv-8URnidzxI3aZviUcAnk_gdT3_INpnH7B5OdrcESHGWyAtMmuEtcpfJ-SFir_MYSo2y5BRmxyuQ_22SxPRGfqPVBThxocb4KHvgUrsgk7jqGl7HOZ4BdajsHU5zpdVLvh1SseEGOGjYS6rfPm6TxQgtX4_TBkp7rdb7LV-EtvkeUILmSXmwEnWsDj91ruYdfrMVTLAWToa-8SVWhugafbHiRKYLcaXWDUB1rhJ1qQtAda0PcqsMbc8xZZsANmiY-V6St-kbQHK12gw-ots8otk6m8wwYJD2KFiK7ydZksMpjsL7XZbJ_TGXzQY9cafdEEWqD3Cl2D102TqdAjhw0wQ0ms39L5L1LmGU9RpMfqPVGEmCtOQJO36v3xNDaJrdD0Nomt1RwzidwvQ3qx2S9xxOkbboGkux4RR2reRKrg9CdazgEkR6qw1y0wNnmdA1a5_RBGbM_jCUxiiOw_pgxSeKv_JTuO8khr_1J43DKF2PwiWIuOoPQXOYyg0yZJbLLFzBJ1mP9VmS-F6Ox_0za6QKb9AxlcUpXZb8XpbLADFpm80yk8krXsAlXJDxIVOKw_dajO1Of68UddkKPm_V-ixeg7X4HU-Btxh93xVJeqwOQHTWN27SNmae1Ak8oQM4aJnQCTlrodcHOW2m3xhJgOEXS3ur3BNHreZHq-JHgOJHreQcfd9Fd5zOACVXmr_xI1i99CxfkMj6LmfL_2XJ-zRnl_gpWpDyKFqSyPsskssEac8IOG6mCUGn2T5xpd4SQnWo2AtDfLPsIoToIYKyFHWazP4jVZjJ-y9djcH0KF-Uxv0yY5nJADRZi87zJVe67E2F6h-AtORGd6kNbqIIOZvTNmrQMWeYzgRpoNk6cqbcQaTdDW7SCDhrnP0xZMX7XpfH_mSaywE0ZZX4XcH1Gkx-o9UYToW78CdXjMX2G02QtecZS3ut4A09cJ3OAlaIuN0QUYO84RRVhbXjGE-I4gc5a5DCBSpcjgBnnhdLxf5k0TOeEkqt4lC6K5bLNKMUfLDmWH2v4QY4e7HhFzxusdYIOmubwPIkSXu-4xVHldstgMkglAtZoQl2yzd95C1x4E-yHHK4EnvjV7EFV5nkKZD5RXjG_VKpHZH1OGziM4a_MH-wJHDFM3nrT4HxOZP_QKj4S5QJatdDuAJuotskjr72SKDhVrwTSJrxRq0fcaPxJW-zIo3WLJzrQ4r-dMo3ruY5bMYqjQZMkOlTx_1NxjaF5ypr4zGb_jKBxQ4_jQdUidgsjwkuYJK36SxRg7UCcetUwCyNsuQqX4294hREbMMsmv5t5Fd8rt4sgKXXBzholsbrHmCFt-c-pxVLf6TXGT5woBhOgqfaHEFzoxWLsOMkVYW-7BxFapzME3jbRrXaDFKEtOUVRXam1_wuXqQNf-RKuTFWiM7_MGCOvuMVR2ye4QY4apzM_jFejsHuH1On2QswY6TVCi9io9MDMWGRwRtAcqTJ-z6sIY35HlOX',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BEarF37wUbUaP3GjyPo9owRw40htn-IHOWutGYLwW4Cy5Ak7fqPVB1O8Kp8XPG6gxfc6X5HDCXLkSa8elrvtH0R2ud4QQon4Z846n8T2Jm_dQG6TxfccTpHJ7iBjl7zuMVaIuh-Nug9ih7n8Yc_0JmnRQ2iazPEjZou971WJwPNXi8L1JVaJ7SJavSKHvvYtYJL3MGeb_2OX-F6Q9S2RwfIiV4u_-FuOxvowZZ0AYsj5Ll6T-CxcwSWKv-8URnidzxI3aZviUcAnk_gdT3_INpnH7B5OdrcESHGWyAtMmuEtcpfJ-SFir_MYSo2y5BRmxyuQ_22SxPRGfqPVBThxocb4KHvgUrsgk7jqGl7HOZ4BdajsHU5zpdVLvh1SseEGOGjYS6rfPm6TxQgtX4_TBkp7rdb7LV-EtvkeUILmSXmwEnWsDj91ruYdfrMVTLAWToa-8SVWhugafbHiRKYLcaXWDUB1rhJ1qQtAda0PcqsMbc8xZZsANmiY-V6St-kbQHK12gw-ots8otk6m8wwYJD2KFiK7ydZksMpjsL7XZbJ_TGXzQY9cafdEEWqD3Cl2D102TqdAjhw0wQ0ms39L5L1LmGU9RpMfqPVGEmCtOQJO36v3xNDaJrdD0Nomt1RwzidwvQ3qx2S9xxOkbboGkux4RR2reRKrg9CdazgEkR6qw1y0wNnmdA1a5_RBGbM_jCUxiiOw_pgxSeKv_JTuO8khr_1J43DKF2PwiWIuOoPQXOYyg0yZJbLLFzBJ1mP9VmS-F6Ox_0za6QKb9AxlcUpXZb8XpbLADFpm80yk8krXsAlXJDxIVOKw_dajO1Of68UddkKPm_V-ixeg7X4HU-Btxh93xVJeqwOQHTWN27SNmae1Ak8oQM4aJnQCTlrodcHOW2m3xhJgOEXS3ur3BNHreZHq-JHgOJHreQcfd9Fd5zOACVXmr_xI1i99CxfkMj6LmfL_2XJ-zRnl_gpWpDyKFqSyPsskssEac8IOG6mCUGn2T5xpd4SQnWo2AtDfLPsIoToIYKyFHWazP4jVZjJ-y9djcH0KF-Uxv0yY5nJADRZi87zJVe67E2F6h-AtORGd6kNbqIIOZvTNmrQMWeYzgRpoNk6cqbcQaTdDW7SCDhrnP0xZMX7XpfH_mSaywE0ZZX4XcH1Gkx-o9UYToW78CdXjMX2G02QtecZS3uu5hNDeKXWB1uNveIVVojB5hlairroHVSN5ww-cJXHCi9hkwVsoxxQygNp1jijF0-y51W_MJvQOagZgbXrXYK05gs9gLbmHEFzttsNP3CgxfcpToDD6BpMmuAyhc4lmRBepg570DyC6TJ25VS3IXe9F4DoXLYKXJ7pLpX-Sn3LAleuIpb6PXHnOIvENYS1KXXKOH7wVIb2PpgERa39UJkOb9xIvQdzp-Apk8P7TaXmW8EYTZ_2S7Ikdqj2KnS4J5LbMaHwSI8Dec88s-s-ccsvkgtRle5YzAJSyzuK7C9w6DagAzeGyhNEkgxZjt0xlA4zZZe87jFWiLoHdvBZxTGSt-kvZJLC5xlJccgxnwNy6VyBs-MxharcDD1tm8vwI2WKvOxDrBpQhKncHkN1pR1Th6zfIUZ4qBqQtegpWorD8SFKb6HRGH3gS7rfEVeJueoaSnur3AEzY6kShOlPvjZbjdMENWWTw-gaTHGj5gs9b6HRBDxpmcz5Kl6y5BY7bq_gFTptrt4OPGyczCZLfa_UBkm3LJgEKV6i',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BEarF37wUbUaP3GjyPo9owRw40htn-IHOWutGYLwW4Cy5Ak7fqPVB1O8Kp8XPG6gxfc6X5HDCXLkSa8elrvtH0R2ud4QQon4Z846n8T2Jm_dQG6TxfccTpHJ7iBjl7zuMVaIuh-Nug9ih7n8Yc_0JmnRQ2iazPEjZou971WJwPNXi8L1JVaJ7SJavSKHvvYtYJL3MGeb_2OX-F6Q9S2RwfIiV4u_-FuOxvowZZ0AYsj5Ll6T-CxcwSWKv-8URnidzxI3aZviUcAnk_gdT3_INpnH7B5OdrcESHGWyAtMmuEtcpfJ-SFir_MYSo2y5BRmxyuQ_22SxPRGfqPVBThxocb4KHvgUrsgk7jqGl7HOZ4BdajsHU5zpdVLvh1SseEGOGjYS6rfPm6TxQgtX4_TBkp7rdb7LV-EtvkeUILmSXmwEnWsDj91ruYdfrMVTLAWToa-8SVWhugafbHiRKYLcaXWDUB1rhJ1qQtAda0PcqsMbc8xZZsANmiY-V6St-kbQHK12gw-ots8otk6m8wwYJD2KFiK7ydZksMpjsL7XZbJ_TGXzQY9cafdEEWqD3Cl2D102TqdAjhw0wQ0ms39L5L1LmGU9RpMfqPVGEuDs9gKTYO35ww-gbPnDD6B9WfcQWaY20_BNpvA8jVajL7vVYW4GlGI7lKz5hlQhLboHk-xFnenCz102Q9DdagKcKLUOGrMMmeeBGnLLmOW91yTyCpjmcsxZ8wBM2bJLFyOs-UXPG6x1gg6b9AAZcv9M5n9NpwCMmuh1w9IrhN01TlpzQE6oAI6b6TVDT9x1jdtzwJkyQA0lcX3Lmeb_jCR8iNTuBl9ruITeZ7QAidZnMHzJVu8IYO57R5QsuQYetsSdtoKQnit4EWn3Aw9dK3dD0V7q90RSoO87SSFu-8fT4C361GK60-G6ySG61GIwCGD6RtAcqTJ-z5jlcf8YZjQAzRsntILb6MJbZ_YCzuczf40lsz-Nmyf0DZvqA1zrNwSSq3lS33iFUmCtuYZTHyv5yBXkMYojMUmVrgZPnCix_k8bZ_TATFlmMwDOGqh1gc9baTY_S9yl8n7XpDxKY7DJFiI6htNsRJGrN0_d9oOdNULPHKoDUR93hZKgOVIgbESdqzcD0Ch1QhpnwI7a6IIPm-l2Ak5nAFlmb7wIkd5vPIpX5TL-zBpmr_xNFmLve8fUoq35xxJeqv_MWGGufosZYq9_i5ejMH4MYuw4hQ5a67TBTepEEfA9G6nDXrcR7vzVov5Y9Q_dN1MvSVZjwEmWIqv4SRaisDlF1p_seMURGmbzfIkZ4y-8D6E1ilyyT20AkqyH3TgJo3WGon4W8UbYbskjABargBCjdI5ou4hb6b7UsY6nuEVi9wvaNkoWc0ZbtwilPgqmuI8qOlRofQ9shOA7GGrF0uEzTdnn_FJiv9lvPFDmu9WyBpMms4YXMs2f9VFlOwzpx1z4FeP4hVv0zav9TmS_HCm9m_fLpDTFIzaRKfbKm636Daw_TKB1Tiy1wk7YJLV-ixeqxqU_WnVNluN0wg2Zou97RVs1UOnFo0AJVeH1SlOgLDhET9vlMcJLmCQ51C-9ChNgMLnGUnB9ytQg8XqHEy-NFmMzf4uZ5XF7hNFdbwhhO9eg7X7LV2Ovu4fT4Cl1wdNtiiN82La_zF3qNkJN2eMvvAVR4qv4RNFdajgDT1wnc4CVoi63xJThLneEVKCsuAQQHDK7yFTeKrtW9A8qM0CRg',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BF6_Jpj9X4S26A0_guhJtSiNsuQnTH6w8l7HNaDF9ylOgMPoGkyYAW_kXIGz5Qo8f6TWCE63KY70Y9sAMmSJu_4jVYfOPawTf-QJO2u0IoWz2Ao8YZPWDjNlqNwBM3abzf9k0v9Up8z-QaYUOWuuFoit3xE2aKvQAjSazgU4nNAHOmqbzjJnnwJnzAM7cqXXPHWs4ESo3D2j1Tpy1gY3Z5zQBD2g0ws_dariRacNPnOj2D1xoQZqzwQ0WYu94hRXfK7gJ5YFbNg9YpTEDXveDDFjk7v8SY222w1Qkd8mcrfcDj5mp_Q4XY_S9ylZqwxw1USy1wk5i8PoGkp9tuYLPW3AJZcAZdj9L1-jDH7jRrrtMWKTuOoakANil_YmS32tHZDvJIOz2ApNcqTUGEuPwPIbQHKkyfs-Y5XHK46-9Ve68VOEuvMrYsP4WpH1W5PLAzZqm8stX8L2J4nrULbqG1KFuvNXuu5QhbryVLfwUbIUdqrgRXut3T6j1_wuYIW3-h9Rg-cggecef-ARdaXVO22dzzRsntcIbtMHQKLbDkJ23BJLgrbsIlWK71S16h2CuR5_4kd9tRhJed8SQnTXOnOm2TpfkcPoGl2QyPgdT5LI_CxRg8b4LFGDxjqsIYar3SCUBnvgBTd6n9EDNJrK_V-WzTOX-Ctelcn7LWOU9lu87FCCuR5UiLrtT7XnGX2vEXes40muEHOo2zyh2A1vqN4QdqwRRnirDnGh0_gqXIGz9htNf7QVRaoQQnjeQnvhR3ew5hxUjfNYuRp-rhJGf-VHf7TpGlKEtht8shRHqQ5FedoKPHOs4EN11jdomP1ewvMnWL7jFUdsnuEGOGqgAWbI_jJjlfcpXb8gV7sfT4e98iWK7CFRgrnyIlSKwPAiVo_IATJpygA0ZJTF_DCWzzCUyzBpyzCWzQVmyC5ghbfpDkCDqNoMQabdFUh5seMXULToTrLkHVCA4RJDedsRQ3ux5BV7tO1SuPEhV4_yKpDCJ1qOx_srXpHB9CxlnNULbdEKa5v9XoO15ww-gbLkGEZ2qt0RSH2v5htMgrLpHUJ0t9wOQKPVNm7TCGmdzS9gkvZXi_EihLwfU7kaUIG37VKJwiNbj8Uqjcb2V7vxIVSF5hpNruRHgLDnTYO06h1OfuFGqt4DNWeMvgE3bqTZEEB1rt8ENnme0AI0ZJfP_Cxhjr_wRHamy_4_carPAkNzo9EGPXbQ9SdZfrDzGEp87lWMBTmz7FK_IYwAOJvQPqgZhLkikQJqntRGa53P9CZpn88FKlyfxPYoWYmu4BI3aazRAzWDyRtutw6C-UeP92S5JWvSG1_OPaAKYKYAadFFn_NFh9IXfuczZrTrQJcLf-MmWtAhdK0ebZ4SXrMhZ9k9b98nge0uluY5gvdYxTGm8FyQyRJ8rOQ2js9EqgE2iN80mw1fkd8TXaEQe8QaitkxeOxiuCWc1CdatBh79Dp-10G16zu0JHPVGFnRH4nsIG-z_C179UJ3xhp99xxOgKXXGj9xo_Bf2UKuGnug0hhNe6vQAjJasRqI7FvSRWqczBpuk8X1JlaEtNkMTnOl1SyVAzltksUHLF6OBjxwlcgKL2GRA3me0RJDc6zaCjNYiroBZsk0o8j6QHKi0wMzZJTF6hxMkvtt0jinH0R2vO0eTnys0QM1WozP9CZYirrtJVKCteITR5vN_yRXmMn-I1aXx_clVYW1DzRmmL3vMqAVge0SR4s',
            'JVqc1PkrbpPF9zyxI5ICZ4y-BFC6L5H9Z8g2l7zuIEV3uiCB7WDF6hxfhLboKpb_bdj9L2GGuPsgUoTQOacclLnrHUJ0t9wOQIbvYcYsmxM4apzB8zZbjb8GdeRLtxxBc6PsWr3rEEJ0mcsORmud4BQ5a67TBTecCjeM3wQ2ed5McaPmTsDlF0luoOMIOmzSBj1w1Ag_cqLTBmqf1zqfBDtzqt0PdK3kGHzgFHXbDXKqDj5vn9QIPHXYC0N3reIafd9FdqvbEHWp2T6iBzxskcP1GkyPtOYYX849pBB1msz8RbMWRGmby_M0gcXuE0WIyRdequ8URnae3yxwlccKL2GR40SoDXzqD0Fxw_sgUoKz4xtLcKLSJYr8Zco9YpTECHHjSKsfUpbH-B1Pf_Vox_xbi7DiEoL1VInoGD1vstcJOX2w9CVWf6TWCC1fosf5K4_yIlm7HlW36B5Xj8YnXL71Wb_3L2eazv8vkcMmWovtT7QaTn-26R5Xux5StOkeVrgbVLUWeNoORKnfEUGiBztgksTpG16DtedLhOVLguNEddkJOZ_RATOY0AI7bNI3a6QGP3Km2kB2r-YaUIa57lO4GU6B5h2C40ar4Rl8rd1DdqbYO57XCj2ew_UnTH7B9CxcgbP2LGCQtecqXJC15yqeEIXqD0GE-GrfRGmb3gM1Z5j-LmHD-jGX-1yPwvktX5HH-Fq_IFC05h2CuOweUbMZS33hE3XbEEetEnTXDD-gBTxx0wxCdNoQdarcD3LVBTdcjsDlF1p_seMYeakOdKbcQqbfRavbFEqAuPFXvB1-4hJ2quNJq-MYTX626Bp_4BZ4qw1yqd0-bqDXEESn2TqbzPxhwiZXi7wiR3mr0AJFapzOBGXKLGKWx_lbjcEjhLsfg7PrIVaJ7lCFteYdVoa47iRUhrrzLGWWzS5kmMj4KWCU-jOU-C-UzS-U-jFpyiySxOkbTXKk5ww-cKUKQXms3RVHe7QYTLIWSIG05EV2p90_daffFUh53xhRthxVhbvzVo70Jou-8itfj8L1JViQyQA5b9E1bs__YcLnGUtwouUWSHyq2g5BdazhE0p_sOYWTYGm2BtAcqQHOZrSN2zNATGTxPZau-9Vhuggg7cdfrTlG1G27SaHv_MpjvEqWrsfVYW46Up-sRJIq-QUS7HnGE6BsuJFqg5CZ5nL8CJlm9IIPXSk2RJDaJrdAjRmmMj_NmOTxfIjVKjaCi9io9UOM2an1wc1aqHaNFmLveIUV3yu4FK58GmdF1C2I4XwZJz_NKIMfegdhvVmzgI4qs8BM1iKzQMzaY7AAyhajL3tEkR2m80QNWeZ5y1_0hty5l2r81vIHYnPNn_DMqEEbsQKZM01qQNXqes2e-JLl8oYT6T7b-NHir40hdgRgtECdsIXhcs9odNDi-VRkvpKneZbvCmVClTA9C124BBImvIzqA5lmuxDmP9xw_VDd8EFdN8ofu49ldxQxhyJADiLvhh831ie4julGU-fGIjXOXy9NYPtUITTF2CR31mm2yp-4VuAsuQJO36j1QdUwz2mEn7fBDZ8sd8PNGaWvhV-7FC_NqnOADB-0vcpWYq66Bg9cLLXCTmQ-Wed0fYpa5DC8mqg1PksbpPF9WfdAjV2p9cQPm6XvO4eZcotmAcsXqTWBjdnl8j4KU6AsPZf0TacC4Oo2iBRgrLgEDVnmb7wM1iKvO4eVYy56SBNfrIGOGqPwgM0aY7BAjJikMDwIHqf0QMoWp0LgOxYfbL2',
        ]

        self.blackbox = 'tra:' + random.choice(blackbox_tokens)
        #    'JVqc1PkrbpPF9zyxI5ICZ4y-BFe4Kov1WtA_ZJbI7R9iyCmVCG2SxAcsXpDSPqcVgKXXCS5go8j6LIPsWr4tpBc8bqDF9zpfkcMIbNM4XY_B5hhbgLLkK5oJcNxBZpjIEX_iEDVnmb7wM2uQwgU5XpDT-CpcwS9csQQpW54DcZbIC3PlCjxuk8UILV-R9ytilfktZJfH-CuPxPxfxClgmM8CNJnSCT2hBTmaADKXzzNjlMT5LWGa_TBonNIHP6IEapvQADWazv5jxyxhkbboGj9xtNkLPYTzYsk1mr_xIWrYO2mOwPAYWabqEzhqre48g88UOWubwwRRlbrsL1SGtghpzTKhDzRmluhAZZfH_DRkibvrPqMVfuNWe63dIYr8YcQ4a6_gETZomA6B4BV0pMn7K5sObaIBMVaIy_AiUpbJDT5vmL3vIUZ4u-ASRKgLO3LUN27QATdwqN9AddcOctgQSICz5xhIqtw_c6QGaM0zZ5jPAjdw1DdrzQI3b9E0bc4vkfMnXcL4Klq7IFR5q90CNHeczgBknf5km_xdjvIiUrjqGkyx6RtUhetQhL0fWIu_81mPyP8zaZ_SB2zRMmea_zab_F_E-jKVxvZcj7_xVLfwI1a33A5AZZfaC0R2psv9QHGh1QUqXJ_RBSpcnxOF-l-Etvlt31S53hBTeKrcDXOj1jhvpgxw0QQ3bqLUBjxtzzSVxSlbkvctYZPGKI7A8laI6lCFvCKH6UyBtBV6seZIgbfpT4XqH1GE50p6rNEDNVqMz_QmWI3uHoPpG1G3G1S6IFCJv_UtZswxkvNXh-sfWL4gWI3C8ytdj_RVi-0gguceUrPjFUyFuRxOrxBBcdY3m8wAMZe87iBFd7rfEUN52j-h1ws8btACNpj5MJT4KGCWy_5jxfoqW5LL-y1jmcn7L2ih2gtCo9kNPW2e1QlvqAltpAlCpAlvpt4_oQc5XpDC5xlcgbPlGn-27iFSirzwKY3BJ4u99ilZuuscUrTqHFSKve5UjcYrkcr6MGjLA2mbADNnoNQEN2qazQU-da7kRqrjRHTWN1yOwOUXWou98R9Pg7bqIVaIv_QlW4vC9htNkLXnGXyuD0es4UJ2pgg5a88wZMr7XZX4LJLzKVqQxitim_w0aJ4DZp_PMJTK-i1ev_Mmh70gWYnAJlyNw_YnV7ofg7fcDkBll9oQR32y6RlOh7jdD1J3qdsNPW-iz_8yX5DEGEp8odQVR3yh1BVJgK7lGE-pzgAyV4nM8SNVxy5l3hKMxSuY-mXZEXSpF4HyXZL7attDd60fRHaozf9CeLDjCDp9otQGN2eMvvAVR4qv4RNepdZCkNUaidwfaN5BdOg6m83-LnrjHF6q3EuC2Ql90DOK_jGS_WHOI2ar5C2Wyzyd9CiV7VeH8ECUDFK1-C1myDR61Cdq3iZ_shmE0zyN9Uy37E-w4hty1BiQ3ECs3Veg9UOs-y6dwvQ6hfAlmP1FkgxutAY5kuhTugZbqfVIm_FjvQQ4o_s-f_dFrxJGldkmn-1nuOs4fNECJ1mLsOIlSnyu-2rkTbklhqvdI1iGttsNPWW8JZP3Zt1QdafXJXme0AAxYY-_5BdZfrDgN6AORHid0BI3aZkRR3ukyfsrbNxMuB102TuG72OIugA1aJ_NADZbjb3lMHjMGWWKvP8kVobyW8YrUIKy-V7BLJvE6RtLjvZo10SpzgBGd6jYBjZklMLyF0l5zC2T9GbP9CZsodQLOWyix_kpbtI5XpDWBzholsb0JVqSyfcrYYa46g9BhKnbDT9vodQBMWSRwvZKfK7TBkd5rtMGR3uz4RFBccvwIlR5q-5c0T2pzgNH'


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
            sys.exit(_('Wrong email or password\n'))

        # get the authentication token and set the cookie
        ses_json = json.loads(r.text, strict=False)
        auth_token = ses_json['token']
        cookie_obj = requests.cookies.create_cookie(domain='.gameforge.com', name='gf-token-production', value=auth_token)
        self.s.cookies.set_cookie(cookie_obj)

        # get accounts
        self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/es_AR/hub', 'Authorization': 'Bearer {}'.format(auth_token), 'DNT': '1', 'Connection': 'close'}
        self.s.headers.clear()
        self.s.headers.update(self.headers)
        r = self.s.get('https://lobby.ikariam.gameforge.com/api/users/me/accounts')
        accounts = json.loads(r.text, strict=False)

        # get servers
        self.headers = {'Host': 'lobby.ikariam.gameforge.com', 'User-Agent': user_agent, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Referer': 'https://lobby.ikariam.gameforge.com/es_AR/hub', 'Authorization': 'Bearer {}'.format(auth_token), 'DNT': '1', 'Connection': 'close'}
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
            resp = self.s.get('https://lobby.ikariam.gameforge.com/api/users/me/loginLink?id={}&server[language]={}&server[number]={}'.format(self.account['id'], self.login_servidor, self.mundo)).text
            resp = json.loads(resp, strict=False)
            if 'url' not in resp:
                if retries > 0:
                    return self.__login(retries-1)
                else:
                    msg = 'Login Error: ' + str(resp)
                    if self.padre:
                        print(msg)
                        sys.exit()
                    else:
                        sys.exit(msg)

            url = resp['url']
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
