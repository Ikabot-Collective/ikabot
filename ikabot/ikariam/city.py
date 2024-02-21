from datetime import datetime
import json
import re
from ikabot.config import materials_names_english
from ikabot.helpers.varios import decodeUnicodeEscape

from typing import TYPE_CHECKING, List, Union, Optional
from ikabot.ikariam.data import Unit, Units
from ikabot.ikariam.player import AvatarScore
if TYPE_CHECKING:
    from ikabot.ikariam.client import Client
    from ikabot.ikariam.island import Island

class City:
    ...


class DropdownCity():
    """Object that contains data about cities that can be gathered from the dropdown menu.
    `luxuryResourceType` and `luxuryResourceName` and will be missing if city isn't own"""
    id: int
    x: int
    y: int
    name: str
    luxuryResourceType: int # only present if is own city
    luxuryResourceName: str # only present if is own city # only god knows why
    isOwnCity: bool
    
    def __init__(self, client: 'Client', dropdownCity: dict) -> None:
        
        self.__client = client
        self.id = int(dropdownCity['id'])
        self.x = int(dropdownCity['coords'].replace('[','').replace(']','').split(':')[0])
        self.y = int(dropdownCity['coords'].replace('[','').replace(']','').split(':')[1])
        self.name = decodeUnicodeEscape(dropdownCity['name']) # ast.literal_eval("'" + dropdownCity['name'].replace('"','').replace("'","") + "'") #this is necessary to process unicode characters properly
        self.isOwnCity = bool(dropdownCity['relationship'] == 'ownCity')
        if self.isOwnCity:
            self.luxuryResourceType = int(dropdownCity['tradegood'])
            self.luxuryResourceName = materials_names_english[self.luxuryResourceType]
    
    def getCity(self) -> City:
        """Sends a request to obtain full data about this city"""

        ...
    
    def selectCity(self) -> City:
        """Selects this dropdown city"""
        
        ...

    ...

# var fleetSpeed =
#                 parseInt(this.transporterSpeed)
#                 * parseFloat(this.worldBonus)
#                 * parseFloat(governmentBonus)
#                 * (1.0 + parseInt(this.tritonInjectorLevel)
#                 + parseFloat(poseidonEffect));

#             var uncappedDuration = Math.ceil(
#                 ((distance * parseInt(fleetJourneyTime)) / fleetSpeed) * this.marineChartArchiveBonus
#             );
#             var calculatedDuration =
#                 uncappedDuration > this.minimumJourneyDuration ? uncappedDuration : this.minimumJourneyDuration;

#             if (transporterDraft.freighters > 0 && transporterCount.selectedFreighters > 0) {
#                 // FREIGHTER_SHIP_BASE_SPEED_FACTOR == 20
#                 this.journeyDuration = calculatedDuration * 20;
#             } else {
#                 this.journeyDuration = calculatedDuration;
#             }

class TransportView():

    journeyDuration: int
    transporterSpeed: int
    baseJourneyTime: int
    distance: float
    loadingSpeed: float
    poseidonBonus: float
    governmentBonus: float
    marineChartArchiveBonus: float
    worldBonus: float
    tritonInjectorLevel: float
    minimumJourneyTime: int
    needsLoading: bool
    queueTime: Optional[datetime]



    def __init__(self, viewData) -> None:

        self.journeyDuration = int(re.search(r"'journeyDuration': (\d+),",viewData).group(1))
        self.transporterSpeed = int(re.search(r"'transportSpeed': (\d+),",viewData).group(1))
        self.baseJourneyTime = int(re.search(r"'fleetJourneyTime': (\d+),",viewData).group(1))
        self.distance = float(re.search(r"'distance': ([\d\.]+),",viewData).group(1))
        self.loadingSpeed = float(re.search(r"'loadingSpeed': ([\d\.]+),",viewData).group(1))
        self.poseidonBonus = float(re.search(r"'poseidonEffect': ([\d\.]+),",viewData).group(1))
        self.governmentBonus = float(re.search(r"'governmentBonus': ([\d\.]+),",viewData).group(1))
        self.marineChartArchiveBonus = float(re.search(r"'marineChartArchiveBonus': ([\d\.]+),",viewData).group(1))
        self.worldBonus = float(re.search(r"'worldBonus': ([\d\.]+),",viewData).group(1))
        self.tritonInjectorLevel = float(re.search(r"'tritonInjectorLevel': ([\d\.]+),",viewData).group(1))
        self.minimumJourneyTime = int(re.search(r"'minimumJourneyDuration': (\d+),",viewData).group(1))
        self.needsLoading = True if int(re.search(r"'needsLoading': (\d+),",viewData).group(1)) == 1 else False
        self.queueTime = datetime.fromtimestamp(int(re.search(r"'queueTime': (\d+),",viewData).group(1)))

        self._transport_view_view_data = viewData
        ...
    
    def getJourneyDuration(self) -> int:
        ...

# $(document).ready(function () {
#                 missionController = new missionController(
#                     0,
#                     500,
#                     546,
#                     0,
#                     3600,
#                     90,
#                     false                );
#                 missionController.updateSummary(0, 0, 0, null, null, null, false, ($("#extraTransporter").length < 1), null);

#                                 create_slider({
#                     dir: 'ltr',
#                     id: "slider_312",
#                     maxValue: 30,
#                     overcharge: 0,
#                     iniValue: 0,
#                     bg: "sliderbg_312",
#                     thumb: "sliderthumb_312",
#                     topConstraint: -10,
#                     bottomConstraint: 326,
#                     bg_value: "actualValue_312",
#                     textfield: "cargo_army_312"
#                 });
#                 var s = ikariam.controller.sliders["slider_312"];
#                 s.upkeep = 11.4;
#                 s.weight = 0;
#                 s.unitJourneyTime = 450;
#                 missionController.registerSlider(s);
#                                 create_slider({
#                     dir: 'ltr',
#                     id: "slider_307",
#                     maxValue: 6,
#                     overcharge: 0,
#                     iniValue: 0,
#                     bg: "sliderbg_307",
#                     thumb: "sliderthumb_307",
#                     topConstraint: -10,
#                     bottomConstraint: 326,
#                     bg_value: "actualValue_307",
#                     textfield: "cargo_army_307"
#                 });
#                 var s = ikariam.controller.sliders["slider_307"];
#                 s.upkeep = 11.4;
#                 s.weight = 0;
#                 s.unitJourneyTime = 900;
#                 missionController.registerSlider(s);
#                             });

class SendUnitsView():

    availableUnits: List[Unit]

    def __init__(self, viewData) -> None:

        availableUnitsMatch = re.search(r"units = JSON.parse\('([\S\s]*?)'\);", viewData.replace('\\"','"').replace('\\/','/'))
        availableUnitsData = json.loads(availableUnitsMatch.group(1))
        self.availableUnits = []
        for unit_id in availableUnitsData:
            self.availableUnits.append(Units.getUnitById(int(unit_id))(availableUnitsData[unit_id].amount))

    # def getJourneyTime(units: List[Unit]) -> int: # TODO Implement this elsewhere, how is the journeytime calculated?
    #     ...






class IslandCityView():
    """Possible actions that can be taken on the IslandCity details view"""

    targetCity: 'IslandCity'
    ownerTitle: Optional[str]
    ownerFlagTag: Optional[str]
    totalScore: int
    hasSpies: bool
    canDiplomacy: bool
    canTransportGoods: bool
    canDefendCity: bool
    canDefendPort: bool
    canPillage: bool
    canOccupyPort: bool
    canOccupyCity: bool
    canSendSpy: bool


    def __init__(self, city: 'IslandCity', data: dict) -> None:
        
        self.targetCity = city
        titleMatch = re.search(r'>([\S\s]*?)<',data['js_selectedCityOwnerTitle']['text'])
        self.ownerTitle = titleMatch.group(1).strip() if titleMatch else None
        flagTagMatch = re.search(r"flag ([\S\s]{1,6}?)'>", data['js_selectedCityOwnerName']['text'])
        self.ownerFlagTag = flagTagMatch.group(1) if flagTagMatch else None
        self.totalScore = int(data['js_selectedCityScore']['text'].replace(',',''))
        self.hasSpies = True if data['js_selectedCityActiveSpies']['class'] != 'invisible' else False
        for row in data:
            if 'href' in row:
                if 'sendIKMessage' in row['href']:
                    self.canDiplomacy = True
                elif 'transport' in row['href']:
                    self.canTransportGoods = True
                elif 'defendCity' in row['href']:
                    self.canDefendCity = True
                elif 'defendPort' in row['href']:
                    self.canDefendPort = True
                elif 'plunder' in row['href']:
                    self.canPillage = True
                elif 'blockade' in row['href']:
                    self.canOccupyPort = True
                elif 'occupy' in row['href']:
                    self.canOccupyCity = True
                elif 'sendSpy' in row['href']:
                    self.canSendSpy = True
            
        #action 9 is attract vermin thing, nobody uses that


        self.__island_city_actions_data = data
        ...
    
    def sendMessage(self): #?view=sendIKMessage&receiverId=234956&isMission=1&closeView=1
        ...
    
    def reportPlayer(self): #?view=reportPlayer&avatarName=Big Tula&isMission=1&closeView=1&avatarId=234956&target=404263 <- cityid
        ...
    
    def sendMessageAlliance(self): #?view=sendIKMessage&allyId=1792&isMission=1
        ...
    
    def transportGoods(self): #?view=transport&isMission=1&destinationCityId=404263
        ...
    
    def defendCity(self): #?view=defendCity&isMission=1&destinationCityId=404263
        ...
    
    def defendPort(self): #?view=defendPort&isMission=1&destinationCityId=404263
        ...

    def pillage(self): #?view=plunder&isMission=1&destinationCityId=404263
        ...
    
    def occupyPort(self): #?view=blockade&isMission=1&destinationCityId=404263
        ...

    def occupyCity(self): #?view=occupy&isMission=1&destinationCityId=404263
        ...

    def sendSpy(self): #?view=sendSpy&isMission=1&destinationCityId=404263&islandId=4193
        ...

    
    ...

class PortOccupier():

    islandCity: 'IslandCity'
    id: int
    name: str
    allianceTag: Optional[str]
    isForeign: bool

    def __init__(self, islandCity: 'IslandCity', data: dict) -> None:
        self.islandCity = islandCity
        self.id = int(data['id'])
        self.name = decodeUnicodeEscape(data['name'].split['['][0]) if '[' in data['name'] else decodeUnicodeEscape(data['name'])
        self.allianceTag = data['name'].split['['][1].replace(']','') if '[' in data['name'] else None
        self.isForeign = True if data['color'] == 'foreignBlocker' else False #could be ownOccupier

        self.__port_occupier_data = data

class CityOccupier():

    islandCity: 'IslandCity'
    id: int
    name: str
    allianceTag: Optional[str]
    isForeign: bool

    def __init__(self, islandCity: 'IslandCity', data: dict) -> None:
        self.islandCity = islandCity
        self.id = int(data['id'])
        self.name = decodeUnicodeEscape(data['name'])
        self.allianceTag = data['tooltip'].split['['][1].replace(']','') if '[' in data['tooltip'] else None
        self.isForeign = True if data['color'] == 'foreignBlocker' else False #could be ownOccupier

        self.__city_occupier_data = data



class IslandPlace(): #TODO what does a city object look like while someone is sending ships to colonize it?

    island: 'Island'
    position: int
    name: str
    isPremiumSpot: bool

    def __init__(self, island: 'Island', position: int, data: dict) -> None:

        self.island = island
        self.position = position
        self.name = "Building ground"
        self.isPremiumSpot = True if data['buildplace_type'] == 'premium' else False

        self.__island_place_data = data
        ...
    
    def colonize(self):

        ...

class IslandCity(IslandPlace, DropdownCity):

    level: int
    ownerId: int
    ownerName: str
    ownerAllianceId: Optional[int]
    ownerAllianceTag: Optional[str]
    hasTreaties: bool
    isInactive: bool
    isVacation: bool
    isGodlyProtection: bool
    isBanned: bool
    isFighting: bool
    isPlagued : bool
    viewableLevel: int
    isPiracyRaidable: bool
    portOccupier: Optional[PortOccupier]
    cityOccupier: Optional[CityOccupier]
    avatarScore: Optional[AvatarScore] #TODO implement this #could be None if player is about to dissapear (vacation and no avatarscore)



    def __init__(self, island: 'Island', position: int, data: dict) -> None:

        IslandPlace.__init__(self, island, position, {'buildplace_type': 'premium' if position == 16 else 'not premium'})

        self.name = decodeUnicodeEscape(data['name'])
        self.id = data['id']
        self.x = island.x
        self.y = island.y
        self.luxuryResourceType = island.luxuryResourceType
        self.luxuryResourceName = island.luxuryResourceName
        self.ownerId = int(data['ownerId'])
        self.isOwnCity = True if self.ownerId == island.__client.userId else False
        self.level = data['level']
        self.ownerNmae = data['ownerName']
        self.ownerAllianceId = data['ownerAllyId'] if data['ownerAllyId'] != 0 else None
        self.ownerAllianceTag = data['ownerAllyTag'] if self.ownerAllianceId else None
        self.hasTreaties = bool(data['hasTreaties'])
        self.isInactive = True if data['status'] == 'inactive' else False
        self.isVacation = True if data['status'] == 'vacation' else False
        self.isGodlyProtection = True if data['status'] == 'noob' else False
        self.isBanned = True if data['status'] == 'inactive_banned' else False
        self.isFighting = True if 'infos' in data and 'armyAction' in data['infos'] and data['infos']['armyAction'] == 'fight' else False
        self.isPlagued = data['infestedByPlague']
        self.viewableLevel = data['viewAble']
        self.isPiracyRaidable = True if 'piracy_raid' in data['actions'] else False

        self.portOccupier = PortOccupier(self, data['infos']['fleetAction']) if 'infos' in data and 'fleetAction' in data['infos'] else None
        self.cityOccupier = CityOccupier(self, data['infos']['occupation']) if 'infos' in data and 'occupation' in data['infos'] else None

        self.avatarScore = [avatarScore for avatarScore in self.island.avatarScores if avatarScore.userId == self.ownerId][0]

        self.__island_city_data = data
    
        
    def selectCity(self) -> City:
        if self.isOwnCity:
            super().selectCity()
        else:
            pass #TODO add log for failure, can't select city that isn't own
    
    def colonize(self):
        pass #TODO add log for failure 

    def getActions(self) -> IslandCityView:

        #TODO validation
        html = self.__client.get(f'view=cityDetails&isMission=1&destinationCityId={self.id}&backgroundView=island&currentIslandId={self.island.id}&templateView=cityDetails&actionRequest=REQUESTID&ajax=1')
        #data = json.loads(re.search(r'updateTemplateData",({[\S\s]*?}})],').group(1))
        data = json.loads(html)[2][1]
        return IslandCityView(self, data)

        ...

    def getPlayer():
        
        ...

    ...

