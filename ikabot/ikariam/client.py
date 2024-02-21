from datetime import datetime
from typing import Callable, List, Optional, Tuple, overload, override
from threading import Thread
import re
import asyncio
import json
from ikabot.ikariam.data import AllianceHighScoreTableRow, MayorMessage, PlayerHighScoreTableRow, HighScoreTypes
from ikabot.ikariam.island import Table
from ikabot.web.session import Session
from ikabot.ikariam.city import DropdownCity
from ikabot.config import materials_names_english




class Client:

    session: Session
    ambrosia: int
    gold: int
    income: int
    badTaxAccountant: int
    plutusGold: int
    scientistsUpkeep: int
    upkeep: int
    totalIncome: int
    premiumGoldBonusPercent: int
    ikariamVersion: str
    freeTransporters: int
    maxTransporters: int
    freeFreighters: int
    maxFreighters: int

    serverName: str
    userId: int
    allianceId: int
    hasPremiumAccount: bool
    additionalWorldMapData: dict

    mayorStatus: str # usually normal or normalactive
    militaryStatus: str
    researchStatus: str
    diplomacyStatus: str

    dropDownCities: List[DropdownCity]
    selectedDropDownCity: DropdownCity



    def __init__(self, session: Session) -> None:
        self.loop_handler = AsyncLoopThread()
        self.loop_handler.start()
        # asyncio.run_coroutine_threadsafe(coroutine(i, randint(3, 5)), loop_handler.loop) # asyncio.sleep to get timeout effect
        self.session: Session = session
        self.__refresh_global_data()
        pass

    def post(self, *args, **kwargs) -> str: #TODO make sure not to send too many requests so as to get temp IP banned.
        response = self.session.post(*args, **kwargs)
        
        #update global data if possible
        self.__load_global_data(response)


    def get(self, *args, **kwargs) -> str:
        response = self.session.get(*args, **kwargs)

        #update global data if possible
        self.__load_global_data(response)

    def __refresh_global_data(self):
        self.__load_global_data(self.get('view=worldmap_iso'))
         
    
    def __load_global_data(self, html):
        ambrosiaMatch = re.search(r'"headlineAmbrosia">(\d+)<', html)
        self.ambrosia = int(ambrosiaMatch.group(1).replace(',','').replace('.','')) if ambrosiaMatch else None
        versionMatch = re.search(r'href="\?view=version"[\S,\s]*?>v([\S,\s]{1,8}?)<\/span>', html)
        self.ikariamVersion = str(versionMatch.group(1)) if versionMatch else None
        freeTransportersMatch = re.search(r'js_GlobalMenu_freeTransporters">(\d+)<\/span>', html)
        self.freeTransporters = int(freeTransportersMatch.group(1).replace(',','').replace('.','')) if freeTransportersMatch else None
        maxTransportersMatch = re.search(r'js_GlobalMenu_maxTransporters">(\d+)<\/span>', html)
        self.maxTransporters = int(maxTransportersMatch.group(1).replace(',','').replace('.','')) if maxTransportersMatch else None
        freeFreightersMatch = re.search(r'js_GlobalMenu_freeFreighters">(\d+)<\/span>', html)
        self.freeFreighters = int(freeFreightersMatch.group(1).replace(',','').replace('.','')) if freeFreightersMatch else None
        maxFreightersMatch = re.search(r'js_GlobalMenu_maxFreighters">(\d+)<\/span>', html)
        self.maxFreighters = int(maxFreightersMatch.group(1).replace(',','').replace('.','')) if maxFreightersMatch else None
        goldMatch = re.search(r'js_GlobalMenu_gold_Total[\S\s]{1,50}?>([\d,-]+)<\/td>', html) # 217,452,933
        self.gold = int(goldMatch.group(1).replace(',','').replace('.','')) if goldMatch else None
        incomeMatch = re.search(r'js_GlobalMenu_income[\S\s]{1,50}?>([\d,-]+)<\/td>', html) # 24,805
        self.income = int(incomeMatch.group(1).replace(',','').replace('.','')) if incomeMatch else None
        badTaxAccountantMatch = re.search(r'js_GlobalMenu_badTaxAccountant[\S\s]{1,50}?>([\d,-]+)<\/td>', html)
        self.badTaxAccountant = int(badTaxAccountantMatch.group(1).replace(',','').replace('.','')) if badTaxAccountantMatch else None
        plutusGoldMatch = re.search(r'js_GlobalMenu_godGoldResult[\S\s]{1,50}?>([\d,-]+)<\/td>', html)
        self.plutusGold = int(plutusGoldMatch.group(1).replace(',','').replace('.','')) if plutusGoldMatch else None
        scientistsUpkeepMatch = re.search(r'js_GlobalMenu_scientistsUpkeep[\S\s]{1,50}?>([\d,-]+)<\/td>', html)
        self.scientistsUpkeep = int(scientistsUpkeepMatch.group(1).replace(',','').replace('.','')) if scientistsUpkeepMatch else None
        upkeepMatch = re.search(r'js_GlobalMenu_upkeep[\S\s]{1,50}?>([\d,-]+)<\/td>', html)
        self.upkeep = int(upkeepMatch.group(1).replace(',','').replace('.','')) if upkeepMatch else None
        totalIncomeMatch = re.search(r'js_GlobalMenu_gold_Calculation[\S\s]{1,50}?>([\d,-]+)<\/td>', html)
        self.totalIncome = int(totalIncomeMatch.group(1).replace(',','').replace('.','')) if totalIncomeMatch else None
        premiumGoldBonusPercentMatch = re.search(r'js_GlobalMenu_production_gold_premiumBonus_value">(\d+)[\S\s]{1,50}?<\/td>', html)
        self.premiumGoldBonusPercent = int(premiumGoldBonusPercentMatch.group(1).replace(',','').replace('.','')) if premiumGoldBonusPercentMatch else None
        
        dataSetForViewMatch = re.search(r'dataSetForView = ', html)
        if dataSetForViewMatch:
             
            serverNameMatch = re.search(r"serverName: '([\S\s]*?)',", html)
            self.serverName = str(serverNameMatch.group(1)) if serverNameMatch else None
            userIdMatch = re.search(r"avatarId: '(\d+)',", html)
            self.userId = int(userIdMatch.group(1)) if userIdMatch else None
            allianceIdMatch = re.search(r"avatarAllyId: '(\d+)',", html)
            self.allianceId = int(allianceIdMatch.group(1)) if allianceIdMatch else None
            hasPremiumAccountMatch = re.search(r"hasPremiumAccount: '',", html) #match exists or doesn't
            self.hasPremiumAccount = False if hasPremiumAccountMatch else True
            
            #Advisor data is missing. Which advisor is highlighted? news? 
            advisorDataMatch = re.search(r"advisorData: JSON\.parse\('([\S\s]*?)'\)", html)
            if advisorDataMatch:
                data = json.loads(advisorDataMatch.group(1).replace('\\"','"'))
                self.militaryStatus = data['military']['cssclass']
                self.mayorStatus = data['cities']['cssclass']
                self.researchStatus = data['research']['cssclass']
                self.diplomacyStatus = data['diplomacy']['cssclass']


            #related city data
            dropdownCityMatch = re.search(r"relatedCityData: JSON\.parse\('([\S\s]*?)'\)", html) 
            if dropdownCityMatch:
                self.dropDownCities = []
                data = json.loads(dropdownCityMatch.group(1).replace('\\"','"'))
                for key in data:
                    if 'city_' in key:
                        self.dropDownCities.append(DropdownCity(self, data[key]))
                        if data['selectedCity'] == key:
                            self.selectedDropDownCity = self.dropDownCities[-1]
                


        #islands data 
        occupiedIslandJSCoordList = re.findall(r"occupiedIslandJS\[(\d+)\]\[(\d+)\] = 1", html)
        occupiedIslandAllyJSCoordList = re.findall(r"occupiedIslandAllyJS\[(\d+)\]\[(\d+)\] = 1", html)
        allyIslandJSCoordList = re.findall(r"allyIslandJS\[(\d+)\]\[(\d+)\] = 1", html)
        ownIslandJSCoordList = re.findall(r"ownIslandJS\[(\d+)\]\[(\d+)\] = 1", html)
        militaryIslandsJSCoordList = re.findall(r"militaryIslandsJS\[(\d+)\]\[(\d+)\] = 1", html)
        warIslandsJSCoordList = re.findall(r"warIslandsJS\[(\d+)\]\[(\d+)\] = 1", html)
        barbarianIslandsJSCoordList = re.findall(r"barbarianIslandsJS\[(\d+)\]\[(\d+)\] = 1", html)
        self.additionalWorldMapData = {
            'occupiedIslandJS': [(int(island[0]), int(island[1])) for island in occupiedIslandJSCoordList],
            'occupiedIslandAllyJS': [(int(island[0]), int(island[1])) for island in occupiedIslandAllyJSCoordList],
            'allyIslandJS': [(int(island[0]), int(island[1])) for island in allyIslandJSCoordList],
            'ownIslandJS': [(int(island[0]), int(island[1])) for island in ownIslandJSCoordList],
            'militaryIslandsJS': [(int(island[0]), int(island[1])) for island in militaryIslandsJSCoordList],
            'warIslandsJS': [(int(island[0]), int(island[1])) for island in warIslandsJSCoordList],
            'barbarianIslandsJS': [(int(island[0]), int(island[1])) for island in barbarianIslandsJSCoordList]
        }

        
        #TODO load friens data, "activeResourceBonuses", 

    def addCoroutine(self, coroutine: Callable[..., None], **kwargs):
         """Add a coroutine to be run in the background. For sleeping use asyncio.sleep() instead of time.sleep()
            otherwise other coroutines will not be able to run while your coroutine is sleeping."""
         asyncio.run_coroutine_threadsafe(coroutine(**kwargs), self.loop_handler.loop)
         

class AsyncLoopThread(Thread):
        def __init__(self):
            super().__init__(daemon=True)
            self.loop = asyncio.new_event_loop()

        def run(self):
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

class PlayerHighScoreTable(Table):

    playerHighScoreView: 'PlayerHighScoreView'
    rows: List[PlayerHighScoreTableRow]

    def __init__(self, playerHighScoreView: 'PlayerHighScoreView', rangeStart: Optional[int], tableHTML: str) -> None:
        self.playerHighScoreView = playerHighScoreView
        super.__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            positionMatch = re.search(r'([\d,]+)', row._cells[0]._content)
            playerTitleMatch = re.search(r'<i>([\S\s]*?)<\/i>', row._cells[1]._content)
            playerFlagTagMatch = re.search(r'flag ([\S\s]{1,5}?)"', row._cells[1]._content)
            playerNameMatch = re.search(r'avatarName">([\S\s]*?)<', row._cells[1]._content)
            playerIdMatch = re.search(r'avatarId=(\d+)', row._cells[1]._content)
            isAllyMatch = re.search(r'ownally', row._class)
            isVacationMatch = re.search(r'b325e463b9e55ec28ebd4f87a87593\.png', row._cells[1]._content)
            isInactiveMatch = re.search(r'score gray', row._cells[3]._class)
            #isBannedMatch = re.search() # TODO what does a banned player look like in the highscore?
            playerAllianceTagMatch = re.search(r'([\S\s]*?)', row._cells[2]._content)
            playerAllianceIdMatch = re.search(r'allyId=(\d+)"', row._cells[2]._content)
            pointsMatch = re.search(r'([\d,]+)', row._cells[3]._content)

            position = int(positionMatch.group(1).strip().replace(',','')) if positionMatch else None
            playerTitle = playerTitleMatch.group(1) if playerTitleMatch else None
            playerFlagTag = playerFlagTagMatch.group(1)
            playerName = playerNameMatch.group(1)
            playerId = int(playerIdMatch.group(1))
            isAlly = True if isAllyMatch else False
            isVacation = True if isVacationMatch else False
            isInactive = True if isInactiveMatch else False
            isBanned = False # TODO fix this
            playerAllianceTag = playerAllianceTagMatch.group(1) if playerAllianceTagMatch and playerAllianceTagMatch.group(1).strip() != '' else None
            playerAllianceId = int(playerAllianceIdMatch.group(1)) if playerAllianceIdMatch else None
            points = int(pointsMatch.group(1).strip().replace(',',''))

            self.rows.append(PlayerHighScoreTableRow(position, playerTitle, playerFlagTag, playerName, playerId, isAlly, isVacation, isInactive, isBanned, playerAllianceTag, playerAllianceId, points))

        

        
        #TODO fix the position being None. If there is at least one player in the table with a known poistion, use it as reference point for other players
        #TODO if that fails then go from beginning to end, pass first position as arg to constructor
        



        ...

class PlayerHighScoreView():

    client: 'Client'
    playerHighScoreTable: PlayerHighScoreTable
    availableRanges: List[Tuple[int, int]]
    currentScoreType: str #check data.highScoreType for available types
    currentRangeStart: int
    currentRangeEnd: int #is always start + 50

    def __init__(self, client: 'Client', viewData: str) -> None:

        self.client = client
        self.__player_high_score_view_data = viewData
        viewData = viewData.replace('\\"','"').replace('\\/','/')

        select_elements = re.findall(r'(<select[\S\s]*?<\/select>)', viewData)
        
        for option in re.findall(r'(<option[\S\s]*?<\/option>)', select_elements[0]):
            if 'selected' in option:
                self.currentScoreType = re.search(r'value="([\S\s]*?)"').group(1)
        
        for option in re.findall(r'(<option[\S\s]*?<\/option>)', select_elements[1]):
            rangeStart = int(re.search(r'value="([\d-]+)"').group(1))
            self.availableRanges.append((rangeStart+1, rangeStart+50))
            if 'selected' in option:
                currentRangeStart = rangeStart if rangeStart != -1 else None

        table = PlayerHighScoreTable(self, currentRangeStart, viewData)
        self.playerHighScoreTable = table
        
        self.currentRangeStart = table.rows[0].position
        self.currentRangeEnd = table.rows[-1].position

    def getNextPage(self) -> 'PlayerHighScoreView':
        ...
    def getFirstPage(self) -> 'PlayerHighScoreView':
        ...
    def getLastPage(self) -> 'PlayerHighScoreView':
        ...
    def setScoreType(self, scoreType: str) -> 'PlayerHighScoreView':
        """Check data.HighScoreTypes for all valid string values for `scoreType`"""
        ...
    @overload
    def getRange(self, range: Tuple[int, int]) -> 'PlayerHighScoreView':
        ...
    @overload
    def getRange(self, start: int, end: int) -> 'PlayerHighScoreView':
        ...
    def searchByUsername(self, username: str) -> 'PlayerHighScoreView':
        ...


    

class AllianceHighScoreTable(Table):

    allianceHighScoreView: 'AllianceHighScoreView'
    rows: List[AllianceHighScoreTableRow]

    def __init__(self, allianceHighScoreView: 'AllianceHighScoreView', rangeStart: Optional[int], tableHTML: str) -> None:
        self.allianceHighScoreView = allianceHighScoreView
        super.__init__(tableHTML)
        self.rows = []
        for row in self._rows:

            positionMatch = re.search(r'([\d,]+)', row._cells[0]._content)
            allianceFlagTagMatch = re.search(r'flag ([\S\s]{1,5}?)"', row._cells[1]._content)
            allianceNameMatch = re.search(r'allyName">([\S\s]*?)<', row._cells[1]._content)
            allianceTagMatch = re.search(r'"\(([\S\s]*?) \)"', row._cells[1]._content)
            allianceIdMatch = re.search(r'allyId=(\d+)', row._cells[1]._content)
            isAllyMatch = re.search(r'ownally', row._class)
            membersMatch = re.search(r'([\d,]+)', row._cells[2]._content)
            pointsMatch = re.search(r'([\d,]+)', row._cells[3]._content)
            averagePointsMatch = re.search(r'([\d,]+)', row._cells[4]._content)
            
            position = int(positionMatch.group(1).strip().replace(',','')) # alliance should not be without position
            allianceFlagTag = allianceFlagTagMatch.group(1)
            allianceName = allianceNameMatch.group(1) if allianceNameMatch else None
            allianceTag = allianceTagMatch.group(1)
            allianceId = int(allianceIdMatch.group(1))
            isAlly = True if isAllyMatch else False
            members = int(membersMatch.group(1).strip().replace(',',''))
            points = int(pointsMatch.group(1).strip().replace(',',''))
            averagePoints = int(averagePointsMatch.group(1).strip().replace(',',''))


            self.rows.append(AllianceHighScoreTableRow(position, allianceFlagTag, allianceName, allianceTag, allianceId, isAlly, members, points, averagePoints))

        ...



class AllianceHighScoreView():

    client: 'Client'
    allianceHighScoreTable: AllianceHighScoreTable
    availableRanges: List[Tuple[int, int]]
    currentScoreType: str #check data.highScoreType for available types
    currentRangeStart: int
    currentRangeEnd: int #is always start + 50



    def __init__(self, client: 'Client', viewData: str) -> None:

        self.client = client
        self.__alliance_high_score_view_data = viewData
        viewData = viewData.replace('\\"','"').replace('\\/','/')


        select_elements = re.findall(r'(<select[\S\s]*?<\/select>)', viewData)
        
        for option in re.findall(r'(<option[\S\s]*?<\/option>)', select_elements[0]):
            if 'selected' in option:
                self.currentScoreType = re.search(r'value="([\S\s]*?)"').group(1)
        
        for option in re.findall(r'(<option[\S\s]*?<\/option>)', select_elements[1]):
            rangeStart = int(re.search(r'value="([\d-]+)"').group(1))
            self.availableRanges.append((rangeStart+1, rangeStart+50))
            if 'selected' in option:
                currentRangeStart = rangeStart if rangeStart != -1 else None




        table = AllianceHighScoreTable(self, currentRangeStart, viewData)
        self.allianceHighScoreTable = table
        
        self.currentRangeStart = table.rows[0].position
        self.currentRangeEnd = table.rows[-1].position

    def getNextPage(self) -> 'AllianceHighScoreView':
        ...
    def getFirstPage(self) -> 'AllianceHighScoreView':
        ...
    def getLastPage(self) -> 'AllianceHighScoreView':
        ...
    def setScoreType(self, scoreType: str) -> 'AllianceHighScoreView':
        """Check data.HighScoreTypes for all valid string values for `scoreType`"""
        ...
    @overload
    def getRange(self, range: Tuple[int, int]) -> 'AllianceHighScoreView':
        ...
    @overload
    def getRange(self, start: int, end: int) -> 'AllianceHighScoreView':
        ...
    def searchByAllianceName(self, name: str) -> 'AllianceHighScoreView':
        ...
    def searchByAllianceTag(self, tag: str) -> 'AllianceHighScoreView':
        ...
    
class MayorMessageTable(Table):

    view: 'MayorView'
    rows: List[MayorMessage]

    def __init__(self, view: 'MayorView', tableHTML: str) -> None:
        self.view = view
        super.__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            typeMatch = re.search(r'category ([\S\s]*?)"', row._cells[0]._content)
            cityNameMatch = re.search(r'>([\S\s]*?)<', row._cells[1]._content)
            cityIdMatch = re.search(r'cityId=(\d+)', row._cells[1]._content)
            dateMatch = re.search(r'"([\d\.\: ]+)"', row._cells[2]._content)
            
            type = typeMatch.group(1)
            cityName = cityNameMatch.group(1).strip()
            cityId = int(cityIdMatch.group(1))
            
            dateStr = dateMatch.group(1).strip()
            date = dateStr.split(' ')[0]
            day = date.split('.')[0]
            month = date.split('.')[1]
            year = date.split('.')[2]
            time = dateStr.split(' ')[-1]
            hour = dateStr.split(':')[0]
            minute = dateStr.split(':')[-1]
            
            subjectHTML = row._cells[3]._content
            self.rows.append(MayorMessage(type, cityName, cityId, datetime(int(year), int(month), int(day), int(hour), int(minute)), subjectHTML))



        ...

class MayorView():

    client: 'Client'
    mayorMessageTable: 'MayorMessageTable'
    currentMessageRange: Tuple[int, int]
    totalMessages: int
    #toggledFilters: List[str] # TODO don't feel like implementing this right now, nobody uses this anyway

    def __init__(self, client: 'Client', viewData: str) -> None:

        self.client = client
        self.__mayor_view_view_data = viewData
        viewData = viewData.replace('\\"','"').replace('\\/','/')

        tableHTML = re.search(r'(<table class="table01 left clearfloat" id="inboxCity"[\S\s]*?<\/table>)', viewData).group(1)
        table = MayorMessageTable(tableHTML)
        self.mayorMessageTable = table

        totalMessagesMatch = re.search(r'class="header">[\S\s]*?\(([\d,]+)\)<\/h3>', viewData)
        self.totalMessages = int(totalMessagesMatch.group(1).replace(',',''))
        
        currentMessageRangeMatch = re.search(r'class="paginator_link bold">(\d+)-(\d+)<\/div>', viewData)
        self.currentMessageRange = (int(currentMessageRangeMatch.group(1)),int(currentMessageRangeMatch.group(2)))

        #TODO missing loading of currently selected filters from HTML


    def getPreviousPage(self) -> 'MayorView':
        ...
    def getNextPage(self) -> 'MayorView':
        ...
    def toggleFilter(self, mayorMessageType: str) -> 'MayorView':
        """Check data.MayorMessageTypes for valid string values of mayorMessageType"""
        ...


