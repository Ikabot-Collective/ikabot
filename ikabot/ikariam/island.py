import json
import re
from ikabot.config import materials_names_english, miracle_names_english
from ikabot.helpers.varios import decodeUnicodeEscape
from datetime import datetime
from typing import TYPE_CHECKING, List, Union, Optional
from ikabot.ikariam.player import AvatarScore
from ikabot.ikariam.city import IslandCity, IslandPlace
from ikabot.ikariam.data import MiracleDontaionTableRow, ResourceDonationTableRow, Resource, Resources, Unit, Units
if TYPE_CHECKING:
    from ikabot.ikariam.client import Client


class WorldMapIsland:
    """Island object that contains data about an island as returned by the World Map View"""

    x: int
    y: int
    id: int
    name: str
    luxuryResourceType: int
    luxuryResourceName: str
    miracleType: int
    miracleName: str
    woodLevel: int
    cityCount: int
    isRed: Optional[bool] # will be none if data is from full island view
    isBlue: Optional[bool]# will be none if data is from full island view
    inRangeOfPiracy: bool
    hasHelios: bool
    hasAlly: bool
    hasCityOccupiedByAlly: bool
    hasOwnCity: bool
    hasCityOccupiedBySelf: bool
    hasTreaty: bool
    isWarIsland: bool
#   isBarbarianFleet: bool Make separate object for barb fleet TODO

    def __init__(self, client: 'Client', x: int, y: int, data: dict) -> None:
        
        self.__client = client
        self.x = int(x)
        self.y = int(y)
        # if bool(int(additionalData['barbarianIslandsJS'])):
        #     self.isBarbarianFleet = True
        #     self.id = -1
        #     return
        # self.isBarbarianFleet = False
        self.hasAlly = (x, y) in client.additionalWorldMapData['allyIslandJS']
        self.hasCityOccupiedByAlly = (x, y) in client.additionalWorldMapData['occupiedIslandAllyJS']
        self.hasOwnCity = (x, y) in client.additionalWorldMapData['ownIslandJS']
        self.hasCityOccupiedBySelf = (x, y) in client.additionalWorldMapData['occupiedIslandJS']
        self.hasTreaty = (x, y) in client.additionalWorldMapData['militaryIslandsJS']
        self.isWarIsland = (x, y) in client.additionalWorldMapData['warIslandsJS']
        self.id = int(data[0])
        self.name = data[1]
        self.luxuryResourceType = int(data[2])
        self.luxuryResourceName = materials_names_english[self.luxuryResourceType]
        self.miracleType = int(data[3])
        self.miracleName = miracle_names_english[self.miracleType]
        # No idea what data[4] and data[5] are. If you find out, open an issue on github and let us know
        self.woodLevel = int(data[6])
        self.cityCount = int(data[7])
        self.inRangeOfPiracy = bool(int(data[8]))
        self.hasHelios = bool(int(data[9])) # data[9] contains either "0" or something like "1768884710", is this the helios id?

        #this is for gauntlet war stuff
        self.isRed = bool(int(data[10]))
        self.isBlue = bool(int(data[11]))

        self.__world_map_data = data

    def getIsland(self) -> 'Island':
        """Gets full island object"""
        ...


# data -->
#        
# [
# "58",         //id 0
# "Phytios",    //name 1
# "1",          //resource type 2
# "2",          //type of miracle 3
# "5",          // ?? 4
# "4",          // ?? 5
# "9",          // lumber level  6
# "12",         // number of people 7
# 0,            // piracy in range 8
# "0",          // helios tower 9
# "0",          // red 10
# "0"           // blue 11
# ]
        
# additionalData -->
#        
# occupiedIslandJS List[tuple(x,y)]
# occupiedIslandAllyJS List[tuple(x,y)]
# allyIslandJS List[tuple(x,y)]
# militaryIslandsJS List[tuple(x,y)]
# warIslandsJS List[tuple(x,y)]
# barbarianIslandsJS List[tuple(x,y)]
        


class TableCell():

    _class: str
    _content: str

    def __init__(self, _class: str, _content: str) -> None:
        self._class = _class
        self._content = _content

class TableRow():

    _class: str
    _cells: List[TableCell]
    
    def __init__(self, _class: str, _cells: str) -> None:
        self._cells = []
        self._class = _class
        class_cells = re.findall(r'<td([\S\s]*?)>([\S\s]*?)<\/td>', _cells)
        for class_cell in class_cells:
            self._cells.append(TableCell(class_cell[0], class_cell[1]))

class Table():

    #_headers: List[TableRow] #won't be doing this too much work, nobody needs headers anyway
    _rows: List[TableRow]
    
    def __init__(self, tableHTML: str) -> None: # '(<table[\S\s]*?<\/table>)' #must be unescaped \" and \/
        self._rows = []
        tbody = re.search(r'<tbody>([\S\s]*?)<\/tbody>', tableHTML)        
        class_rows = re.findall(r'<tr([\S\s]*?)>([\S\s]*?)<\/tr>', tbody.group(1))
        for class_row in class_rows:
            self._rows.append(TableRow(class_row[0], class_row[1]))

class ResourceDonationTable(Table):

    resourceView: 'ResourceView'
    rows: List[ResourceDonationTableRow]


    def __init__(self, resourceView: 'ResourceView', tableHTML: str) -> None:
        self.resourceView = resourceView
        super().__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            playerFlagTagMatch = re.search(r'flag ([\S\s]{1,6}?)">', row._cells[0]._content)
            playerNameMatch = re.search(r'avatarName">([\S\s]*?)<', row._cells[0]._content)
            playerIdMatch = re.search(r'avatarId=(\d+)"', row._cells[0]._content)
            playerCityNameMatch = re.search(r'([\S\s]*?)', row._cells[1]._content)
            playerCityLevelMatch = re.search(r'(\d+)', row._cells[2]._content)
            playerCityWorkersMatch = re.search(r'(\d+)', row._cells[3]._content)
            donatedMatch = re.search(r'"([\d,]+) ', row._cells[4]._content)

            playerFlagTag = playerFlagTagMatch.group(1) if playerFlagTagMatch else self.rows[-1].playerFlagTag
            playerName = playerNameMatch.group(1) if playerNameMatch else self.rows[-1].playerName
            playerId = int(playerIdMatch.group(1)) if playerIdMatch else self.rows[-1].playerId
            playerCityName = playerCityNameMatch.group(1)
            playerCityLevel = int(playerCityLevelMatch.group(1))
            playerCityWorkers = int(playerCityWorkersMatch.group(1))
            donated = int(donatedMatch.group(1).replace(',',''))

            self.rows.append(ResourceDonationTableRow(playerFlagTag, playerName, playerId, playerCityName, playerCityLevel, playerCityWorkers, donated))
        ...
    ...

class ResourceView():

    island: 'Island'
    sliderMaxSkilledWorkers: int
    sliderMaxUnskilledWorkers: int
    sliderMaxWorkers: int
    sliderCurrentWorkers: int
    citizensAvailable: int
    basicProduction: int
    unskilledWorkersProduction: int
    serverProductionBonusPercent: int
    premiumProductionBonusPercent: int
    adVideoProductionBonusPercent: int
    heliosTowerProductionBonusPercent: int
    godProductionBonusPercent: int
    totalProduction: int
    canDonate: bool
    maxDonation: int

    requiredForNextLevel: int
    availableDonated: int
    
    donationTable: ResourceDonationTable

    def __init__(self, island: 'Island', updateTemplateData: dict, viewData: str) -> None:

        self.island = island
        
        #TODO test this, it might be wrong
        self.sliderMaxSkilledWorkers = int(updateTemplateData['js_ResourceSlider']['slider']['max_value'])
        self.sliderMaxUnskilledWorkers = int(updateTemplateData['js_ResourceSlider']['slider']['overcharge'])
        self.sliderMaxWorkers = self.sliderMaxSkilledWorkers + self.sliderMaxUnskilledWorkers
        self.sliderCurrentWorkers = int(updateTemplateData['js_ResourceSlider']['slider']['ini_value'])
        self.citizensAvailable = int(updateTemplateData['valueCitizens'])
        self.basicProduction = int(float(updateTemplateData['js_resource_tooltip_basic_production']['text']))
        self.unskilledWorkersProduction = int(float(updateTemplateData['js_resource_tooltip_overload_production']['text']))
        self.serverProductionBonusPercent = int(float(updateTemplateData['js_resource_tooltip_server_production_bonus']['text'].replace('+','').replace('%','').replace('-','').strip()))
        self.premiumProductionBonusPercent = int(float(updateTemplateData['js_resource_tooltip_premium_production_bonus']['text'].replace('+','').replace('%','').replace('-','').strip()))
        self.adVideoProductionBonusPercent = int(float(updateTemplateData['js_resource_tooltip_adVideo_production_bonus']['text'].replace('+','').replace('%','').replace('-','').strip()))
        self.heliosTowerProductionBonusPercent = int(float(updateTemplateData['js_resource_tooltip_helios_tower_bonus']['text'].replace('+','').replace('%','').replace('-','').strip()))
        self.godProductionBonusPercent = int(float(updateTemplateData['js_resource_tooltip_god_bonus']['text'].replace('+','').replace('%','').replace('-','').strip()))
        self.totalProduction = int(updateTemplateData['js_resource_tooltip_total_production']['text'])
        self.canDonate = bool(json.loads(updateTemplateData['load_js']['params'].replace('\\"','"'))['canDonate'])
        self.maxDonation = int(json.loads(updateTemplateData['load_js']['params'].replace('\\"','"'))['maxDonation'])

        required_available = re.findall(r'class="wood">([\S\s]*?)<', viewData.replace('\\"','"').replace('\\/','/'))
        self.requiredForNextLevel = int(required_available[0].replace(',','').strip())
        self.availableDonated = int(required_available[1].replace(',','').strip())

        self.donationTable = ResourceDonationTable(self, updateTemplateData['donationTableContainer'].replace('\\"','"').replace('\\/','/'))

        self.__luxury_resource_view_template_data = updateTemplateData
        self.__luxury_resource_view_view_data = viewData

        

        ...

    def setWorkers(self, workers: int):
        ...
    def donateWood(self, wood: int):
        ...

    ...

class MiracleDontaionTable(Table):

    miracleView: 'MiracleView'
    rows: List[MiracleDontaionTableRow]

    def __init__(self, miracleView: 'MiracleView', tableHTML: str) -> None:
        self.miracleView = miracleView
        super().__init__(tableHTML)
        self.rows = []
        for row in self._rows:

            playerFlagTagMatch = re.search(r'flag ([\S\s]{1,6}?)">', row._cells[0]._content)
            playerNameMatch = re.search(r'avatarName">([\S\s]*?)<', row._cells[0]._content)
            playerIdMatch = re.search(r'avatarId=(\d+)"', row._cells[0]._content)
            playerCityNameMatch = re.search(r'([\S\s]*?)', row._cells[1]._content)
            donatedMatch = re.search(r'" ([\d,]+) "', row._cells[2]._content)
            priestsMatch = re.search(r'([\d,]+)', row._cells[3]._content)
            conversationPercentMatch = re.search(r'([\d\.]+)', row._cells[4]._content)
            conversionIslandSharePercentMatch = re.search(r'([\d\.]+)', row._cells[5]._content)

            playerFlagTag = playerFlagTagMatch.group(1) if playerFlagTagMatch else self.rows[-1].playerFlagTag
            playerName = playerNameMatch.group(1) if playerNameMatch else self.rows[-1].playerName
            playerId = int(playerIdMatch.group(1)) if playerIdMatch else self.rows[-1].playerId
            playerCityName = playerCityNameMatch.group(1)
            donated = int(donatedMatch.group(1).replace(',','')) if donatedMatch else self.rows[-1].donated
            priests = int(priestsMatch.group(1).replace(',',''))
            conversationPercent = float(conversationPercentMatch.group(1))
            conversionIslandSharePercent = float(conversionIslandSharePercentMatch.group(1))

            self.rows.append(ResourceDonationTableRow(playerFlagTag, playerName, playerId, playerCityName, donated, priests, conversationPercent, conversionIslandSharePercent))
        ...
    ...

class MiracleView():

    island: 'Island'
    faithPercentage: int
    faithLevel: int
    requiredForNextLevel: Optional[int]
    availableDonated: Optional[int]
    donationTable: MiracleDontaionTable

    def __init__(self, island: 'Island', updateTemplateData: dict, viewData: str) -> None:
        
        self.island = island
        self.faithPercentage = int(re.search(r'(\d+)', updateTemplateData['wonderBeliefInfo2']).group(1))
        self.faithLevel = int(re.search(r'wonderLevelDisplay[\S\s]{1,50}?(\d+)<', viewData.replace('\\"','"').replace('\\/','/')).group(1))
        self.requiredForNextLevel = int(updateTemplateData['js_donateNextLevel'].replace(',','')) if 'js_donateNextLevel' in updateTemplateData else None
        self.availableDonated = int(updateTemplateData['js_donatedResources'].replace(',','')) if 'js_donatedResources' in updateTemplateData else None
        self.donationTable = MiracleDontaionTable(self, re.search(r'(<table[\S\s]*?</table>)',viewData.replace('\\"','"').replace('\\/','/')).group(1))
        
        self.__miracle_view_template_data = updateTemplateData
        self.__miracle_view_view_data = viewData


    def donate(self, wine: int, crystal: int, sulphur: int):
        ...



class BarbarianVillageView():

    barbarianVillage: 'BarbarianVillage'
    isPillagable: bool
    revengeProbability: Optional[str] # This is optional because there is no revenge up to level 10
    resources: List[Resource]
    units: List[Unit]
    wallLevel: Optional[int] # no wall up to level 10

    def __init__(self, barbarianVillage: 'BarbarianVillage', updateTemplateData: dict, viewData: str) -> None:

        self.barbarianVillage = barbarianVillage
        self.isPillagable = False if 'js_islandBarbarianPlundering' in updateTemplateData and updateTemplateData['js_islandBarbarianPlundering']['href'] == 'javascript:void(0);' else True
        self.revengeProbability = updateTemplateData['barbarianKingRevenge']['text'] if 'barbarianKingRevenge' in updateTemplateData else None

        gold = int(updateTemplateData['js_islandBarbarianResourcegold']['text'].replace(',','')) if 'js_islandBarbarianResourcegold' in updateTemplateData else 0
        wood = int(updateTemplateData['js_islandBarbarianResourceresource']['text'].replace(',','')) if 'js_islandBarbarianResourceresource' in updateTemplateData else 0
        wine = int(updateTemplateData['js_islandBarbarianResourcetradegood1']['text'].replace(',','')) if 'js_islandBarbarianResourcetradegood1' in updateTemplateData else 0
        marble = int(updateTemplateData['js_islandBarbarianResourcetradegood2']['text'].replace(',','')) if 'js_islandBarbarianResourcetradegood2' in updateTemplateData else 0
        crystal = int(updateTemplateData['js_islandBarbarianResourcetradegood3']['text'].replace(',','')) if 'js_islandBarbarianResourcetradegood3' in updateTemplateData else 0
        sulphur = int(updateTemplateData['js_islandBarbarianResourcetradegood4']['text'].replace(',','')) if 'js_islandBarbarianResourcetradegood4' in updateTemplateData else 0
        self.resources = [Resources.Gold(gold), Resources.Wood(wood), Resources.Wine(wine), Resources.Marble(marble), Resources.Crystal(crystal), Resources.Sulphur(sulphur)]


        tableHTML = re.search(r'(<table class="table01 militaryList">[\S\s]*?<\/table>)', viewData.replace('\\"','"').replace('\\/','/')).group(1)
        table = Table(tableHTML)
        unit_ids = re.findall(r'army s(\d+)', tableHTML)
        if '314' in unit_ids:
            unit_ids.remove('314') # we don't want the wall
        unit_counts = []
        for cell in table._rows[1]._cells:
            content = cell._content.replace(',','').strip()
            if content.isdigit():
                unit_counts.append(unit_counts)
            else:
                self.wallLevel = int(re.search(r'(\d+)', content).group(1))

        self.units = []
        for i, unit_id in enumerate(unit_ids):
            self.units.append(Units.getUnitById(int(unit_id))(int(unit_counts[i])))

        self.__barbarian_village_view_template_data = updateTemplateData
        self.__barbarian_village_view_view_data = viewData

    def pillage(self, units: List[Unit]): #view=plunder&destinationCityId=0&barbarianVillage=1&islandId=1234
        ...
    def ceaseFire(): # won't be implemeting this
        ...
    def shadyMerchant():# won't be implementing this
        ...

    ...

class BarbarianVillage():
    """Barbarian village object. `kingName` and `isDestroyed` will be `None` if it's on a foreign island."""

    island: 'Island'
    name: str
    visible: bool
    numberOfBarbarians: int #this is the sum of all their units #don't know this if it's not on your island
    wallLevel: int                 #don't know this if it's not on your island
    level: int                     #don't know this if it's not on your island
    isUnderAttack: bool            #don't know this if it's not on your island
    isLuxuryResourceSiege: bool    #don't know this if it's not on your island
    kingName: Optional[str]     #don't know this if it's not on your island
    isDestroyed: Optional[bool] #don't know this if it's not on your island

    def __init__(self, island: 'Island', data: dict) -> None:
        self.island = island
        self.name = 'Barbarian Village'
        self.visible = True if data['invisible'] == 0 else False
        self.numberOfBarbarians = data['count']
        self.wallLevel = data['wallLevel']
        self.level = data['level']
        self.isUnderAttack = True if data['underAttack'] == 1 else False
        self.isLuxuryResourceSiege = True if data['isTradegoodSiege'] == 1 else False
        self.kingName = data['city'] if 'city' in data else None
        if 'destroyed' in data:
            self.isDestroyed = True if data['destroyed'] == 1 else False
        else:
            self.isDestroyed = None


        self.__barbarian_village_data = data
    
    def getBarbarianVillageView(self) -> BarbarianVillageView:
        ...

class HeliosTower():
    "Helios tower class. `owner` will be `None` if is not built."

    island: 'Island'
    isBuilt: bool
    top: int
    mid: int
    base: int
    name: str
    tooltip: str
    isActive: bool
    ownerName: Optional[str]

    def __init__(self, island: 'Island', data: dict) -> None:
        self.island = island
        self.isBuilt = bool(data['isHeliosTowerBuilt'])
        self.top = int(data['heliosTop'])
        self.mid = int(data['heliosMid'])
        self.base = int(data['heliosBase'])
        self.name = decodeUnicodeEscape(data['heliosName'])
        self.tooltip = data['heliosTooltip'] # "Helios Tower activated", "Helios Tower not activated"
        self.isActive = True if data['heliosActive'] == 1 else False
        self.ownerName = self.name.split("'")[0] if "'" in self.name else None # "SeaStar's Helios Tower"
        # [player for player in island.islandCities if player.ownerName == ownerName][0] # won't be doing this because owner might have moved colony

        self.__helios_tower_data = data


class Island(WorldMapIsland):
    """Island object that contains the full data about an island when viewed from the island view. 
    `isRed` and `isBlue` will be `None`, as that data is only returned by the world map and not by the detailed island view."""

    luxuryResourceLevel: int
    miracleLevel: int
    woodBonusActive: bool
    luxuryResourceBonusActive: bool
    luxuryResourceEndUpgradeTime: Optional[datetime]
    woodEndUpgradeTime: Optional[datetime]
    miracleEndUpgradeTime: Optional[datetime]
    heliosTower: HeliosTower
    barbarianVillage: BarbarianVillage
    avatarScores: List[AvatarScore]
    islandPlaces: List[Union[IslandCity, IslandPlace]]

    
    def __init__(self, client: 'Client', data: dict) -> None:
        
        self.__client = client
        self.x = int(data['xCoord'])
        self.y = int(data['yCoord'])
        self.id = int(data['id'])
        self.name = data['name']
        self.luxuryResourceType = int(data['tradegood'])
        self.luxuryResourceName = materials_names_english[self.luxuryResourceType]
        self.miracleType = int(data['wonder'])
        self.miracleName = miracle_names_english[self.miracleType]
        self.woodLevel = int(data['resourceLevel'])
        self.isRed = None  # no data for this in full island view
        self.isBlue = None # no data for this in full island view
        self.hasHelios = data['isHeliosTowerBuilt']
        self.hasAlly = (self.x, self.y) in client.additionalWorldMapData['allyIslandJS']
        self.hasCityOccupiedByAlly = (self.x, self.y) in client.additionalWorldMapData['occupiedIslandAllyJS']
        self.hasOwnCity = (self.x, self.y) in client.additionalWorldMapData['ownIslandJS']
        self.hasCityOccupiedBySelf = (self.x, self.y) in client.additionalWorldMapData['occupiedIslandJS']
        self.hasTreaty = (self.x, self.y) in client.additionalWorldMapData['militaryIslandsJS']
        self.isWarIsland = (self.x, self.y) in client.additionalWorldMapData['warIslandsJS']

        self.luxuryResourceLevel = int(data['tradegoodLevel'])
        self.miracleLevel = int(data['wonderLevel'])
        self.woodBonusActive = True if data['showResourceBonusIcon'] == 1 else False
        self.luxuryResourceBonusActive = True if data['showTradegoodBonusIcon'] == 1 else False
        self.luxuryResourceEndUpgradeTime = datetime.fromtimestamp(int(data['tradegoodEndUpgradeTime'])) if int(data['tradegoodEndUpgradeTime']) == 0 else None
        self.woodEndUpgradeTime = datetime.fromtimestamp(int(data['resourceEndUpgradeTime'])) if int(data['resourceEndUpgradeTime']) == 0 else None
        self.miracleEndUpgradeTime = datetime.fromtimestamp(int(data['wonderEndUpgradeTime'])) if int(data['wonderEndUpgradeTime']) == 0 else None
        self.heliosTower = HeliosTower(self, data)
        self.barbarianVillage = BarbarianVillage(self, data)
        self.avatarScores = [AvatarScore(avatarScore) for avatarScore in list(data['avatarScores'].values())]
        
        self.islandPlaces = []
        for pos, islandSpot in enumerate(data['cities']):
            if islandSpot['type'] == 'city':
                self.islandPlaces.append(IslandCity(self, pos, islandSpot))
            elif islandSpot['type'] == 'empty':
                self.islandPlaces.append(IslandPlace(self, pos, islandSpot))

        self.cityCount = len(self.getCities())
        self.inRangeOfPiracy = any([city.isPiracyRaidable for city in self.getCities()])


        self.__island_data = data
        ...

    def getCities(self) -> List[IslandCity]:
        return [city for city in self.islandPlaces if type(city) is IslandCity]
    
    def getEmptyPlaces(self) -> List[IslandPlace]:
        return [city for city in self.islandPlaces if type(city) is IslandPlace]
    
    def getLuxuryResourceView(self) -> ResourceView:
        #TODO prevent clicking this if it's upgrading, that's gonna cause issues 100%
        ...
    def getWoodResourceView(self) -> ResourceView:
        #TODO prevent clicking this if it's upgrading, that's gonna cause issues 100%
        ...
    def getMiracleView(self) -> MiracleView:
        ...
    ...