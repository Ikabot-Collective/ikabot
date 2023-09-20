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
import traceback
import base64
from ikabot import config
from ikabot.config import *
from collections import deque
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import banner
from ikabot.helpers.aesCipher import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.getJson import getCity
from ikabot.helpers.varios import getDateTime
from urllib3.exceptions import InsecureRequestWarning

t = gettext.translation('session', localedir, languages=languages, fallback=True)
_ = t.gettext

#blackbox tokens
blackbox_tokens = [ #ch, chi, ffi
    'JVqc1fosb5TG-D2yJJMDaI2_BVi5K4z2W9FAZZfJ7iBjySqWCW6TxQgtX5HTP6gWgabYCi9hpMn7LYTtW78upRg9b6HG-DtgksQHb-FQvSJHeavQAkVqnM4VhPNaxitQgrL7acz6H1GDqNodVXqs7yBSd6nsEUN13U98xBY7bbAYiq_hJIn3JHnM8SNmyzlekMLnGVyBs-VLf7bpTYG46xtMf-MYULMYfbTsI1aI7SZdkfVZje5Uhusjh7foGE2Bte5RhLzwJluT9li-7yRUie4iUrcbgLXlCjxuk8UILV-R2Ee2HYnuE0V1viyPveIURGyt-j5njL4BQpDXI2iNv-8XWKXpDkCDqNoKXL0hhvVjiLrqPJS56xtQiLjdDz-S92nSN6rPATF13lC1GIy_AzRlirzsYtU0acj4HU9_72LB9lWFqtwfRHam6h1hksPsEUN1mswPNGaY_WCXzjRpzwAwZJTFKIvB8SOG6x-EuR6B5kp9s-wcULYafOFHe7HpHoG2GE2vEUGl3j-i2DyiAzRlnQJjyPpflrvtH0R2ud4QQqbfQKbdPp_QNGSU-ixcjvMrXZbHLZLG_2GazQE1m9EKQXWr4RRJrhN0qdxBeN0-oQY8dNcIOJ7RATOW-TJlmPkeUIKn2RxNhrjoDT-Cs-MXR2ye4RNHbJ7hBjhqmwExZMb9NJr-X5LF_DBilMr7XcIjU7fpIIW77yFUthxOgOQWeN4TSrAVd9oPQqMIP3TWD0V33RN4rd8SddgIOl-Rw-gaXYK05ht8rBF3qd9FqeJIrt4XTYO79Fq_IIHlFXmt5kyu5htQgbnrHYLjGXuuEHWs4EFxo9oTR6rcPZ7P_2TFKVqOvyVKfK7TBUhtn9E1mtI0ZcgtXb4iWIzCKIvuI1m67yOFuu5RhbfuUrTlSq4SRqrfQXLUC0R3qt9BcqsPQHWo2Als0DOYyf5iw_YnTH6w1QdKb6HTCG2k3A9AeKreF3uvFXmr5BdHqNkKQKLYCkJ4q9xCe7QZf7joHla58VeJ7iFVjsLyJViIu_MsY5zSNJjRMmLEJUp8rtMFSHmr3w09caTYD0R2reITSXmw5Ak7fqPVB2qc_TWazzBklPYnWb0eUrjpS4PmGoDhF0h-tBlQieoiVozxVI29HoK46BtMreEUdasOR3euFEp7seQVRagNcaXK_C5Thcj5LWCZyf8vYZrQ9Sdqj8HzJVWHuucXUH2v3zNknMH0NWqgxfg5aaHPAThqxOkbTXKk5ww-cKgSivho4FrO_23dRbjsUr0podlQyi2l3Ea17hNFd5zOEUJ6sNUHSm-h0wQ0WYu94hRXfK7gOmy5KXnyPKn8LmKT4Dap2yhs3DJ_sgxClgROmP1SqPxFieJKpNUnmvEkjAVWicsbfcMJc8s4abATjMUshclAsP5UxPhdtAI3nPE2oAJFisEKhPRBph9pwRhLnQxe1yF3wAdRthmE2RJnvfYmidEnnfNhpwpVwjZot-c0pPxTpMn7PaPpK1u1-Dmx_2nUBVK8CTuI3DVptvphk7jqHEFzttsNP4z7dd5Kthc8brTpF0dsns72TbYkiPdu4QY4aLYKL2GRwvIgUHWo6g9Bccgxn9UJLmGjyPoqotgMNVqMvP1t3UmuBWrMF4D0GUuRxvkwXpHH7B5OdsEJXar2G02QtecXg-xXvOETQ4rvUr0sVXqs3B-H-WjVOl-R1wg5b53N-ytZia7gEGPEKov9Zou9AzhrotADOV6QwucZXIGz5RdHeazZCUJvodElVo6z5idckrfqK1uTwfEhUavQAjRZi848sR2JruMn',
    'JVqc1fosb5TG-D2yJJMDaI2_BVi5K4z2W9FAZZfJ7iBjySqWCW6TxQgtX5HTP6gWgabYCi9hpMn7LYTtW78upRg9b6HG-DtgksQHb-FQvSJHeavQAkVqnM4VhPNaxitQgrL7acz6H1GDqNodVXqs7yBSd6nsEUN13U98xBY7bZ_E9jlekMIoXJPGKl6VyPgpXMD1LZD1WpHJADNlygM6btI2assxY8gAZJTF9SpekssuYZnNAzhw0zWbzAExZsv_L5T4XZLC5xlLcKLlCjxutSST-mbL8CJSmwlsmr_xIUmK1xtEaZveH220AEVqnMz0NYLG6x1ghbfnOZr-Y9JAZZfHGXGWyPgtZZW67Bxv1EavFIes3g5Suy2S9Wmc4BFCZ5nJP7IRRqXV-ixczD-e0zJih7n8IVODx_o-b6DJ7iBSd6nsEUN12j10qxFGrN0NQXGiBWiezgBjyPxhlvtewydakMn5LZP3Wb4kWI7G-16T9SqM7h6Cuxx_tRl_4BFCet9Apdc8c5jK_CFTlrvtH4O8HYO6G3ytEUFx1wk5a9AIOnOkCm-j3D53qt4SeK7nHlKIvvEmi_BRhrkeVbobfuMZUbTlFXuu3hBz1g9Cddb7LV-EtvkqY5XF6hxfkMD0JEl7vvAkSXu-4xVHeN4OQaPaEXfbPG-i2Q0_cafYOp8AMJTG_WKYzP4xk_krXcHzVbvwJ43yVLfsH4DlHFGz7CJUuvBVirzvUrXlFzxuoMX3Ol-Rw_hZie5Uhrwihr8li7v0KmCY0Tec_V7C8laKwymLw_gtXpbI-l_A9liL7VKJvR5OgLfwJIe5Gnus3EGiBjdrnAInWYuw4iVKfK4Sd68RQqUKOpv_NWmfBWjLADaXzABil8suYpTLL5HCJ4vvI4e8Hk-x6CFUh7weT4jsHVKFteZJrRB1pts_oNMEKVuNsuQnTH6w5UqBuewdVYe79FiM8laIwfQkhbbnHX-15x9ViLkfWJH2XJXF-zOWzjRmy_4ya5_PAjVlmNAJQHmvEXWuDz-hAidZi7DiJVaIvOoaToG17CFTir_wJlaNweYYW4Cy5Ed52hJ3rA1BcdMENpr7L5XGKGDD912-9CVbkfYtZsf_M2nOMWqa-1-Vxfgpir7xUojrJFSL8SdYjsHyIoXqToKn2QswYqXWCj12ptwMPnet0gRHbJ7QAjJkl8T0LVqMvBBBeJ3QEUV-o9YXSXyq3RVIosf5K1CCxeocTrcaj8Y3acs8qt1AqhB15FrG9mbOOKcUgvlc0vcpW4Cy9SdYia7gI0h6rN0NMmSWu-0wVYe5DYfYQaX7SZLnF1CdAjRlvBVZyDN9xCeR5DtwtAdPsiV76ClOgMYnoeNTrBWEqdsdcN0ya8AFWtMcTbn6TpPELpEKO68FSI4BZrsiiuMVhfxHsQJ4zv5AsgJVyEKV2yxewQhz60Cp2UOl6EKS4CV7zhhKsvVBlgkuYKYKUavvPpTlXa8FWpHiULz9VJfYUJ4Ic6TxW6ghbsIblOMncOgNP3GWyAswYpThUMoznwtskcMJPmycwfMjS6ILed1MwzZbjb0LX4S25hdHdaXK_T9klsYdhvQqXoO2-B1Pf_ctYYqv4RFSwjKeA1q_IWzVSW6g5htOhbPmHEFzo8sWXrL_S3Ci5Qo8bNhBrBE2aJjfRKcSgarPATF03E69Ko-05ixdjsTyIlCArt4DNWW4GX_gUrvgEliNwPclWI6z5Rc8brHWCDpsnM4BLl6XxPYmeqviBzp7r-gNQIGz5hREdKT-I1WHrN4hjwRw3AE2eg',
    'JVqc1fosb5TG-D2yJJMDaI2_BVi5K4z2W9FAZZfJ7iBjiLrsHUJ0psv9QGWXyRB12EOy1wk7YJLV-ixetR6M8F_WSW6g0vcpbJHD9TukFnvhUMjtH1F2qOsQQnSZy_0iVJfH7B5hksTpG16DtedMuuc8j7TmKY78IVOFqtwfRHaoDkJ5rBBEe67eD0Km2xN220B3r-YZS7DpIFS4HFCxF0mu5kp6q9sQRHixFEd_s-keVrkbgbLnF0yx5RV63kN4qM3_MVaIy_AiVJsKeeBMsdYIOIHvUoCl1wcvcL0BKk-BxAVTmuYrUIKy2htorNEDRmudzR-A5Em4Jkt9rf84XY-_8SFRdqjYK5ACa9BDaJrKDnfpTrElWJzN_iNVhftuzQJhkbboGIj7Wo_uHkdsntD1J2qPwfMkWIjpHlS371SJ71GC40l5quEUet9CcqQKa6QIbqQJO53UBjZqnP00mP4wYJPFK2KX0AFimP5jlvcvk_UtkcosUYO12gxPdKbYCGrQCGmZzi9mySpik8b_Npj5LmCX-Fq87k-Gu_FWhrzyJ1u_9idYkMcojL_zI4a58CWK7yWK7E6xFU2w6CFTg6jaDDFjptcQQnKXyQw9baHR9ihrndH2KGuQwvQli7vuUIe-JIjpHE-GuuweVIXnTK3dQXOqD0V5q95AptgKbqACaJ3UOp8BZJnMLZLJ_mCZzwFnnQI3aZz_YpLE6RtNcqTnDD5w0wpApdcJbM8FZscAZpv8Mmeg2BFCe7PmSH-2GX2t5Rp7ruQXS68TSa_lHlGJwfMqi-0ig7caULPpGnux4xuAtdoMPmOV2P0vYcctjvIlWInA9SWJwfIlirwfgbgeTrTkG1S17CNWu-0kVoe68yZWvOweVrfqHH2w4BVKe64UR3ziQ6TbP3DSAmSJu-0SRIes3hBIfuBFqgtxowk8baYLPm7QB2vRNpr9M2jLLpDJ-SuMxf02l8n6KpD2WIvvI1mNxShgkPJWhr_xIoPkFHWn4BNFapzO8yVom9D-NWig0wU-c6zfD0h6rNEDRmudzzJkxf1il_gsXL7vIYXmGoCxE0uu4kip3xBGfOEYUbLqHlS5HFWF5kqAsOMUdancPXPWDz923BJDeazdDXDVOW2SxPYbTZDB-ipclMf3L1-Wu-0wVYe56xtNgK3dFkN1pfkqYoe6-zBhhrn6LV2LwvUlf6TWCC1fosf5K6AQiL8kng137SCM-FyO9le67yBRty2VADFq4QY4ao_BBDVmnMHzNluNv_AgRXepzgBDaJrMMHe4KHbNNKQIXa_fKW6zI2_FG4bpMH3zRrQbUJnwZ5j-QY_wOacBabbnF4zkUKkbdN1QwSZsxv1IsgN63iOH3jWNAUqg9z2v_EF14SyDuyKExxVHme07kfVvxDeE2UC5Elmi1yBn2k2WAVaG0wR06zewJGzRFUm-GIW-AFmhCW63Ini-EFOUDFrEL2CtF2SV5CiTClerADFWiLrfEVR5q90qmRN86FS12gxSh7XlCjxslOtUwiaVDH-k1gZUqM3_L2CQvu4TRoit3w9mzz1zp8z_QWaYyEB2qs8CRGmbyz2z2AtMfa3mFERtksT0O6ADbt0CNHqs3A09bZ7O_yRWhsw1pwxy4Vl-sPYnWI-97RJEdpvNEDVnmcv7LWCNvfYjVYXZCkJnmtsQQWaZ2g09a5vL-1V6rN4DNXjmW8czWI3R',
# this one no longer works?    'JVqc1PkrbpPF9zyxI5ICZ4y-BFe4Kov1WtA_ZJbI7R9iyCmVCG2SxAcsXpDSPqcVgKXXCS5go8j6LIPsWr4tpBc8bqDF9zpfkcMGbuBPvCFGeKrPAURpm80Ug_JZxSpPgbH6aMv5HlCCp9kcVHmr7iJHebzhE0WtH0yU5gs9b5TGCS5gkvgsY5b6LmWYyPkskMX9YMUqYZnQAzWa0wo-ogY6mwEzmNA0ZJXF-i5im_4xaZ3TCECjBWuc0QE2m8__ZMgtYpK36RtAcrXaDD6F9GPKNpvA8iJr2Txqj8HxGVqn6xQ5a67vPYTQFTpsnMQFUpa77TBVh7cJas4zohA1Z5fpQWaYyP01ZYq87D-kFn_kV3yu3iKL_WLFOWyw4RI3aZkPguEWdaXK_CycD26jAjJXiczxI1OXyg4_cJm-8CJHebzhE0WpDDxz1Thv0QI4cangQXbYD3PZEUmBtOgZSavdQHSlB2nONGiZ0AM4cdU4bM4DOHDSNW7PMJL0KF7D-StbvCFVeqzeAzV4nc8BZZ7_ZZz9Xo_zI1O56xtNsuocVYbsUYW-IFmMwPRakMkANGqg0wht0jNomwA3nP1gxfszlsf3XZDA8lW48SRXuN0PQWaY2wxFd6fM_kFyotYGK12g0gYrXaAUhvtghbf6buBVut8RVHmr3Q50pNc5cKcNcdIFOG-j1Qc9btA1lsYqXJP4LmKUxymPwfNXietRhr0jiOpNgrUWe7LnSYK46lCG6yBShehLe63SBDZbjdD1J1mO7x-E6hxSuBxVuyFRisD2LmfNMpP0WIjsIFm_IVmOw_QsXpD1VozuIYPoH1O05BZNhrodT7ARQnLXOJzNATKYve8hRni74BJEettAotgMPW_RAzeZ-jGV-Slhl8z_ZMb7K1yTzPwuZJrK_DBpotsMQ6TaDj5un9YKcKkKbqUKQ6UKcKffQKIIOl-Rw-gaXYK05huAt-8iU4u98SqOwiiMvvcqWrvsHVO16x1Vi77vVY7HLJLL-zFpzARqnAE0aKHVBThrm84GP3av5Uer5EV11zhdj8HmGFuMvvIgUIS36yJXicD1JlyMw_ccTpG26Bp9rxBIreJDd6cJOmzQMWXL_F6W-S2T9CpbkccsY5z9NWmfBGeg0DGVy_suX8D0J4i-IVqKwSddjsT3KFi7IIS43Q9BZpjbDT1uodgQSHux6A0_gqfZCz1tn9L_L2KPwfVJeqzRBEV4rNEERXWu3AxDdtD1J1l-sPMYSnzrWsk3oA112Al_40246iOUCj-k1k-F617BIoit3xE2aKvfF090pukOQHKj0_gqXIGz9htNf-RRir8hZa_4XMc_tABEicEjVKoec6QQiO1azQBWqg5VpiCQCFfBNGzBCVe4HYjBN4zTOrEGN5_gQa_gTK0WfsgUfuZbwBNkibsBV8MNP5TZSav6P7brQa0De8cebKD3TqAWZs8ZXrDhNqMGSb0AWqH7NIX-M3_XGoLaJpP7TKXoHYnfSb0OaKvsZLIcf7QCbMU9ivRFeMZAiQInWYuw4iVKfK77auRNuSWGq90jWIa22w09Zbwlk_dm3VB1p9cleZ7QADFhj7_kF1l-sOA3oA5EeJ3QEjdpmRFHe6TJ-yts3Ey4HXTZO4bvY4i6ADVon80ANluNveUweMwZZYq8_yRWhvJbxitQgrL5XsEsm8TpG0uO9mjXRKnOAEZ3qNkHN2WVw_MYSnrNLpT1Z9D1J22i1Qw6baPI-ixRg8brHU-BseMWQ3Om0wU5jb7wFUiJvPAVSIm58R9Pf68JLmCSt-ksmg975wxBhQ',
]

class Session:
    def __init__(self):
        if isWindows:
            self.logfile = os.getenv('temp') + '/ikabot.log'
        else:
            self.logfile = '/tmp/ikabot.log'
        self.padre = True
        self.logged = False
        self.blackbox = 'tra:' + random.choice(blackbox_tokens)
        self.requestHistory = deque(maxlen=5) #keep last 5 requests in history
        # disable ssl verification warning
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        self.__login()

    def setStatus(self, message):
        """This function will modify the current tasks status message that appears in the table on the main menu
        Parameters
        ----------
        message : Message to be displayed in the table in main menu
        """
        self.writeLog('Changing status to {message}', __name__, level=logLevels.INFO, logRequestHistory=True)

        # read from file
        sessionData = self.getSessionData()
        try:
            fileList = sessionData['processList']
        except KeyError:
            fileList = []
        # modify current process' status message
        [p.update({'status': message}) for p in fileList if p['pid'] == os.getpid()]
        # dump back to session data
        sessionData['processList'] = fileList
        self.setSessionData(sessionData)

    def writeLog(self, msg, module = __name__, level = logLevels.INFO, logTraceback = False, logRequestHistory = False):
        """Writes a log entry.
        Parameters
        ----------
        msg : str
            The message to be logged, usually the reason for writing to log file
        module : str
            Name of module from which function is called
        level : str
            The severity of the message (can be ERROR, WARN, INFO, DEBUG). If it's lower than the currently set log level, the entry **WILL NOT BE CREATED**
        logTraceback : bool
            Boolean indicating whether or not to include the call stack printout in the log entry
        logRequestHistory : bool
            Boolean indicating whether or not to attach last 5 requests and their responses to this log entry.
        """
        if not (type(level) is int and level >= self.logLevel):
            return
        entry = {'level': level, 'date': getDateTime(), 'pid': os.getpid(), 'message': msg, 'module': module, 'traceback': traceback.format_exc() if logTraceback else None, 'request_history': json.dumps(list(self.requestHistory)) if logRequestHistory else None}
        try:
            with open(self.logfile,'a') as file:
                json.dump(entry, file)
                file.write('\n')
        except:
            pass # If we can't write to the file, then do nothing. feelsbadman
    
    def updateLogLevel(self, level = None):
        """Updates the sessions logging level, WARN by default. If none is passed, will load level from session data."""
        sessionData = self.getSessionData()
        if 'shared' not in sessionData:
            sessionData['shared'] = {}
        if level is None and 'logLevel' in sessionData['shared']:
            self.logLevel = sessionData['shared']['logLevel']
            return
        elif level is None and 'logLevel' not in sessionData['shared']:
            #set to warn by default
            level = config.logLevel #logLevels.WARN
        self.logLevel = level
        sessionData['shared']['logLevel'] = level
        
        self.setSessionData(sessionData['shared'], shared = True)

    def getLogs(self, level = 0, page = 0, perPage = 25, sort = 'date'):
        """Gets logs from logfile.
        Parameters
        ----------
        level : int
            Returns only logs of this level or higher
        page : int
            Page of logs to return
        perPage : int
            Number of log entries to return per page
        sort : str
            String that indicates by which property of log to sort. Attack - to the beginning for reverse order
            
        Returns
        -------
        logs :  [dict]
            List of log entry objects with properties: "level", "date", "pid", "message", "module", "traceback", "request_history"
        """
        with open(self.logfile, 'r') as f:
            logs = [json.loads(line) for line in f]
        logs = [log for log in logs if log['level'] >= level]
        reverse = False if sort.count('-') % 2 == 0 else True  # check how many minuses sort has, even = correct order, odd = reverse order
        sort = sort.replace('-','')                            # remove - from sort
        logs.sort(key=lambda log: log[sort], reverse = reverse)
        logs = logs[page * perPage : page * perPage + perPage]
        return logs

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
            if self.s.get('https://lobby.ikariam.gameforge.com/api/users/me').status_code == 200:
                return True
            self.s.cookies.clear()
        return False

    def __login(self, retries=0):
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
        self.updateLogLevel()
        self.writeLog('__login()')

        #test to see if the lobby cookie in the session file is valid, this will save time on login and will reduce use of blackbox token
        sessionData = self.getSessionData()
        if 'shared' in sessionData and 'lobby' in sessionData['shared']:
            cookie_obj = requests.cookies.create_cookie(domain='.gameforge.com', name='gf-token-production', value=sessionData['shared']['lobby']['gf-token-production'])
            self.s.cookies.set_cookie(cookie_obj)

        
        if not self.__test_lobby_cookie():

            self.writeLog('Getting new lobby cookie', level = logLevels.WARN)

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
                            self.writeLog("Failed to solve interactive captcha!", level=logLevels.ERROR)
                            print("Failed to solve interactive captcha, trying again!")
                            continue
                        else:
                            break

            if r.status_code == 403:
                print('Failed to log in...')
                print('Log into the lobby via browser and then press CTRL + SHIFT + J to open up the javascript console')
                print('If you can not open the console using CTRL + SHIFT + J then press F12 to open Dev Tools')
                print('In the dev tools there should be a tab called "Console". Press this tab.')
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
        else:
            self.writeLog('Using old lobby cookie')

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
                self.writeLog('using old cookies')
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
            self.writeLog('using new cookies', level = logLevels.WARN)
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
            self.blackbox = 'tra:' + random.choice(blackbox_tokens)
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
            skipGetCookie = False
            if 'url' not in respJson:
                if retries > 0:
                    return self.__login(retries-1)
                else:                               # 403 is for bad user/pass and 400 is bad blackbox token?
                    msg = 'Login Error: ' + str(resp.status_code) + ' ' + str(resp.reason) + ' ' + str(resp.text)
                    self.writeLog(msg, level = logLevels.ERROR)
                    if self.padre:
                        print(msg)
                        print('Failed to log in... Do you want to provide the cookie manually? (Y|N): ')
                        choice = read(values=['y','Y','n','N'], empty=False)
                        if choice in ['n','N']:
                            sys.exit(msg)
                        while True:
                            print('Log into the account via browser and then press F12 to open up the dev tools')
                            print('In the dev tools click the tab "Application" if on Chrome or "Storage" if on Firefox')
                            print('Within this window, there should be a dropdown menu called "Cookies" on the far left.')
                            print('Find the "ikariam" cookie and paste it below:')
                            
                            ikariam_cookie = read(msg='\nEnter ikariam cookie manually: ').split('=')[-1]
                            cookie_obj = requests.cookies.create_cookie(domain=self.host, name='ikariam', value=ikariam_cookie)
                            self.s.cookies.set_cookie(cookie_obj)
                            try:
                                # make a request to check the connection
                                html = self.s.get(self.urlBase, verify=config.do_ssl_verify).text
                            except Exception:
                                self.__proxy_error()
                            skipGetCookie = cookies_are_valid = self.__isExpired(html) is False
                            if not cookies_are_valid:
                                print('This cookie is expired. Do you want to try again? (Y|N): ')
                                choice = read(values=['y','Y','n','N'], empty=False)
                                if choice in ['n','N']:
                                    sys.exit(msg)
                                continue
                            # TODO check if account is actually the one associated with this email / pass
                            break
                    else:
                        self.writeLog('I wanted to ask user for ikariam cookie but he wasn\'t looking', level = logLevels.ERROR)
                        sys.exit(msg)

            if not skipGetCookie:
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
        self.writeLog('__backoff()')
        if self.padre is False:
            time.sleep(5 * random.randint(0, 10))

    def __sessionExpired(self):
        self.writeLog('__sessionExpired()')
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
        self.writeLog('__checkCookie()')
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
        fullResponse : bool
            if set to True it will retrn the full response object instead of the string containing html or json data

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
        while True:
            try:
                self.requestHistory.append({'method': 'GET', 'url': url, 'params': params, 'payload': None, 'proxies': self.s.proxies, 'headers': dict(self.s.headers), 'response': None})
                self.writeLog('About to send: {}'.format(str(self.requestHistory[-1])))
                response = self.s.get(url, params=params, verify=config.do_ssl_verify)
                self.requestHistory[-1]['response'] = {'status': response.status_code, 'elapsed': response.elapsed.total_seconds(), 'headers': dict(response.headers), 'text': response.text}
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
        while True:
            try:
                self.requestHistory.append({'method': 'POST', 'url': url, 'params': params, 'payload': payloadPost, 'proxies': self.s.proxies, 'headers': dict(self.s.headers), 'response': None})
                self.writeLog('About to send: {}'.format(str(self.requestHistory[-1])))
                response = self.s.post(url, data=payloadPost, params=params, verify=config.do_ssl_verify)
                self.requestHistory[-1]['response'] = {'status': response.status_code, 'elapsed': response.elapsed.total_seconds(), 'headers': dict(response.headers), 'text': response.text}
                resp = response.text
                if ignoreExpire is False:
                    assert self.__isExpired(resp) is False
                if 'TXT_ERROR_WRONG_REQUEST_ID' in resp:
                    self.writeLog(_('got TXT_ERROR_WRONG_REQUEST_ID, bad actionRequest'), level = logLevels.WARN, logRequestHistory = True)
                    return self.post(url=url_original, payloadPost=payloadPost_original, params=params_original, ignoreExpire=ignoreExpire, noIndex=noIndex)
                return resp
            except AssertionError:
                self.__sessionExpired()
            except requests.exceptions.ConnectionError:
                time.sleep(ConnectionError_wait)

    def logout(self):
        """This function kills the current (chlid) process
        """
        self.writeLog('logout({})')
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