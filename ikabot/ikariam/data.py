from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime
from typing import List, Optional, overload

@dataclass()
class Resource(): #TODO test if this is actually usable as an int #inherit from int
    """Represents a single Ikariam resource type and quantity."""

    id: int
    name: str
    cssClass: str
    count: int

    def __int__(self):
        return self.count
    def __call__(self, count: int) -> 'Resource':
        copy = deepcopy(self)
        copy.count = count
        return copy

class Resources():
    """Container and factory for standard Ikariam resource types."""

    Wood: Resource = Resource(0, 'Wood', 'wood', 0)
    Wine: Resource = Resource(1, 'Wine', 'wine', 0)
    Marble: Resource = Resource(2, 'Marble', 'marble', 0)
    Crystal: Resource = Resource(3, 'Crystal', 'glass', 0)
    Sulphur: Resource = Resource(4, 'Sulphur', 'sulfur', 0)
    Gold: Resource = Resource(5, 'Gold', 'gold', 0)
    Citizens: Resource = Resource(6, 'Citizens', 'citizens', 0)
    #TODO add ambro and action points and capture points and research points and pirate crew

    def __init__(self, wood: int = 0, wine: int = 0, marble: int = 0, crystal: int = 0, sulphur: int = 0, gold: int = 0, citizens: int = 0) -> None:

        self.Wood = Resources.Wood(wood)
        self.Wine = Resources.Wine(wine)
        self.Marble = Resources.Marble(marble)
        self.Crystal = Resources.Crystal(crystal)
        self.Sulphur = Resources.Sulphur(sulphur)
        self.Gold = Resources.Gold(gold)
        self.Citizens = Resources.Citizens(citizens)
    
    @staticmethod
    def getResourceByCssClass(cssClass: str) -> Optional[Resource]:
        for resource in Resources.__dict__.values():
            if type(resource) is Resource and resource.cssClass == cssClass:
                return resource
        return None
    @staticmethod
    def getResourceByName(name: str) -> Optional[Resource]:
        for resource in Resources.__dict__.values():
            if type(resource) is Resource and resource.name == name:
                return resource

@dataclass()
class Unit():
    """Represents a military unit or ship type with optional quantity."""

    id: int
    name: str
    cssClass: str
    count: int
    isBarbarianUnit: Optional[bool] # This is optional because a wall is a neutral unit
    isShip: bool
    productionCost: Optional[Resources]
    upkeep: Optional[int]
    weight: Optional[int]
    requiredBuildingLevel: Optional[int]
    buildingTime: Optional[int]
    speed: Optional[int]
    size: Optional[int]

    def __call__(self, count: int) -> 'Unit': # This is so that a new unit can be instantiated with `Units.Unit_Name(25)`
        copy = deepcopy(self)
        copy.count = count
        return copy
    
    def __str__(self) -> str:
        return self.name

class Units():
    """Unit factory. Create a unit like so: 20 Slingers -> `Units.Slinger(20)` or 30 Spearmen -> `Units.getUnitById(315)(30)`"""

    Slinger: Unit = Unit(301, 'Slinger', 'slinger', 0, False, False, Resources(wood=20, citizens=1), 2, 3, 2, 90, 60, 1)
    Archer: Unit = Unit(313, 'Archer', 'archer', 0, False, False, Resources(wood=30, sulphur=25, citizens=1), 4, 5, 7, 4*60, 60, 1)
    Sulphur_Carabineer: Unit = Unit(304, 'Sulphur_Carabineer', 'marksman', 0, False, False, Resources(wood=50, sulphur=150, citizens=1), 3, 5, 13, 10*60, 60, 4)
    Spearman: Unit = Unit(315, 'Spearman', 'spearman', 0, False, False, Resources(wood=30, citizens=1), 1, 3, 1, 60, 60, 1)
    Swordsman: Unit = Unit(302, 'Swordsman', 'swordsman', 0, False, False, Resources(wood=30, sulphur=30, citizens=1), 4, 3, 6, 3*60, 60, 1)
    Hoplite: Unit = Unit(303, 'Hoplite', 'phalanx', 0, False, False, Resources(wood=40, sulphur=30, citizens=1), 3, 5, 4, 5*60, 60, 1)
    Steam_Giant: Unit = Unit(308, 'Steam Giant', 'steamgiant', 0, False, False, Resources(wood=130, sulphur=180, citizens=2), 12, 15, 12, 15*60, 40, 3)
    Gyrocopter: Unit = Unit(312, 'Gyrocopter', 'gyrocopter', 0, False, False, Resources(wood=25, sulphur=100, citizens=3), 15, 15, 10, 15*60, 80, 1)
    Balloon_Bombardier: Unit = Unit(309, 'Balloon Bombardier', 'bombardier', 0, False, False, Resources(wood=40, sulphur=250, citizens=5), 45, 30, 11, 30*60, 20, 2)
    Battering_Ram: Unit = Unit(307, 'Battering Ram', 'ram', 0, False, False, Resources(wood=220, citizens=5), 15, 30, 3, 10*60, 40, 5)
    Catapult: Unit = Unit(306, 'Catapult', 'catapult', 0, False, False, Resources(wood=260, sulphur=300, citizens=5), 25, 30, 8, 30*60, 40, 5)
    Mortar: Unit = Unit(305, 'Mortar', 'mortar', 0, False, False, Resources(wood=260, sulphur=300, citizens=5), 25, 30, 8, 30*60, 40, 5)
    Doctor: Unit = Unit(311, 'Doctor', 'medic', 0, False, False, Resources(wood=50, crystal=450, citizens=1), 20, 10, 9, 20*60, 60, 1)
    Cook: Unit = Unit(310, 'Cook', 'cook', 0, False, False, Resources(wood=50, wine=150, citizens=1), 10, 20, 5, 20*60, 40, 2)
    Spartan: Unit = Unit(319, 'Spartan', 'spartan', 0, False, False, Resources(wood=40, sulphur=40, citizens=1), 0, 5, None, None, 60, 1)

    Merchant_Ships: Unit = Unit(201, 'Merchant Ships', 'ship_transport', 0, False, True, Resources(), None, None, None, None, 66, 1)
    Freighter: Unit = Unit(204, 'Freighter', 'ship_freighter', 0, False, True, Resources(), None, None, None, None, 4, 1)
    Ram_Ship: Unit = Unit(210, 'Ram Ship', 'ship_ram', 0, False, True, Resources(wood=250, citizens=3), 15, None, 1, 40*60, 40, 3)
    Ballista_Ship: Unit = Unit(213, 'Ballista Ship', 'ship_ballista', 0, False, True, Resources(wood=180, sulphur=160, citizens=6), 20, None, 3, 50*60, 40, 2)
    Fire_Ship: Unit = Unit(211, 'Fire Ship', 'ship_flamethrower', 0, False, True, Resources(wood=80, sulphur=230, citizens=4), 25, None, 4, 30*60, 40, 2)
    Catapult_Ship: Unit = Unit(214, 'Catapult Ship', 'ship_catapult', 0, False, True, Resources(wood=180, sulphur=140, citizens=5), 35, None, 3, 50*60, 40, 3)
    Mortar_Ship: Unit = Unit(215, 'Mortar Ship', 'ship_mortar', 0, False, True, Resources(wood=220, sulphur=900, citizens=5), 50, None, 17, 50*60, 30, 4)
    Steam_Ram: Unit = Unit(216, 'Steam Ram', 'ship_steamboat', 0, False, True, Resources(wood=400, sulphur=800, citizens=2), 45, None, 15, 40*60, 40, 5)
    Rocket_Ship: Unit = Unit(217, 'Rocket Ship', 'ship_rocketship', 0, False, True, Resources(wood=200, sulphur=1200, citizens=2), 55, None, 11, 1*60*60, 30, 4)
    Diving_Boat: Unit = Unit(212, 'Diving Boat', 'ship_submarine', 0, False, True, Resources(wood=160, sulphur=100, crystal=750, citizens=3), 50, None, 19, 1*60*60, 40, 3)
    Paddle_Speedboat: Unit = Unit(218, 'Paddle Speedboat', 'ship_paddlespeedship', 0, False, True, Resources(wood=40, sulphur=280, citizens=1), 5, None, 13, 30*60, 60, 1)
    Balloon_Carrier: Unit = Unit(219, 'Balloon Carrier', 'ship_ballooncarrier', 0, False, True, Resources(wood=700, sulphur=700, citizens=8), 100, None, 7, 1*60*60 + 6*60, 20, 5)
    Tender: Unit = Unit(220, 'Tender', 'ship_tender', 0, False, True, Resources(wood=300, sulphur=250, crystal=250, citizens=7), 100, None, 9, 40*60, 30, 6)

    Barbarian_Axe_Swinger: Unit = Unit(316, 'Barbarian_Axe_Swinger', 'barbarian', 0, True, False, None, None, None, None, None, 60, 1)
    Barbarian_Clubman: Unit = Unit(320, 'Barbarian_Clubman', 'barbarianClub', 0, True, False, None, None, None, None, None, 60, 1)
    Barbarian_Knifeman: Unit = Unit(321, 'Barbarian_Knifeman', 'barbarianKnive', 0, True, False, None, None, None, None, None, 60, 1)
    Barbarian_Axe_Thrower: Unit = Unit(322, 'Barbarian_Axe_Thrower', 'barbarianAxethrow', 0, True, False, None, None, None, None, None, 60, 1)
    Barbarian_War_Walker: Unit = Unit(323, 'Barbarian_War_Walker', 'barbarianWalker', 0, True, False, None, None, None, None, None, 40, 3)
    Barbarian_Ram: Unit = Unit(324, 'Barbarian_Ram', 'barbarianRam', 0, True, False, None, None, None, None, None, 40, 5)
    Barbarian_Catapult: Unit = Unit(325, 'Barbarian_Catapult', 'barbarianCatapult', 0, True, False, None, None, None, None, None, 40, 5)
    Barbarian_Dirigible: Unit = Unit(327, 'Barbarian_Dirigible', 'barbarianZeppelin', 0, True, False, None, None, None, None, None, 20, 2)
    Barbarian_Fighter: Unit = Unit(326, 'Barbarian_Fighter', 'barbarianFighter', 0, True, False, None, None, None, None, None, 80, 1)

    Deckwrecker: Unit = Unit(221, 'Deckwrecker', 'ship_barbarian_light_battleship', 0, True, True, None, None, None, None, None, 40, 3)
    Sail_Shredder: Unit = Unit(222, 'Sail_Shredder', 'ship_barbarian_light_ranged', 0, True, True, None, None, None, None, None, 40, 2)
    Pyroboat: Unit = Unit(223, 'Pyroboat', 'ship_barbarian_heavy_battleship', 0, True, True, None, None, None, None, None, 40, 2)
    Boulder_Catapult: Unit = Unit(224, 'Boulder_Catapult', 'ship_barbarian_heavy_ranged', 0, True, True, None, None, None, None, None, 40, 3)
    Wedge_Paddler: Unit = Unit(225, 'Wedge_Paddler', 'ship_barbarian_heavy_battleship_II', 0, True, True, None, None, None, None, None, 40, 4)
    Powder_Pitcher: Unit = Unit(226, 'Powder_Pitcher', 'ship_barbarian_heavy_ranged_II', 0, True, True, None, None, None, None, None, 30, 4)
    Terror_of_the_Deep: Unit = Unit(227, 'Terror_of_the_Deep', 'ship_barbarian_first_strike_I', 0, True, True, None, None, None, None, None, 40, 3)
    Dragonfire: Unit = Unit(228, 'Dragonfire', 'ship_barbarian_first_strike_II', 0, True, True, None, None, None, None, None, 30, 4)
    Dirigible_Igniter: Unit = Unit(229, 'Dirigible_Igniter', 'ship_barbarian_anti_carrier', 0, True, True, None, None, None, None, None, 60, 1)
    Barbarian_Nest: Unit = Unit(230, 'Barbarian_Nest', 'ship_barbarian_carrier', 0, True, True, None, None, None, None, None, 20, 5)

    Wall: Unit = Unit(314, 'Wall', 'wall', 0, None, False, None, None, None, None, None, None, None)

    @staticmethod
    def getUnitById(id: int) -> Optional[Unit]:
        for unit in Units.__dict__.values():
            if type(unit) is Unit and unit.id == id:
                return unit
        return None
    @staticmethod
    def getUnitByName(name: str) -> Optional[Unit]:
        for unit in Units.__dict__.values():
            if type(unit) is Unit and unit.name == name:
                return unit
        return None
    @staticmethod
    def getUnitByCssClass(cssClass: str) -> Optional[Unit]:
        for unit in Units.__dict__.values():
            if type(unit) is Unit and unit.cssClass == cssClass:
                return unit
        return None

@dataclass()
class ResourceDonationTableRow():
    """Row in an island sawmill or luxury mine donation table."""
    
    playerFlagTag: str
    playerName: str
    playerId: int
    playerCityName: str
    playerCityLevel: int
    playerCityWorkers: int
    donated: int

@dataclass()
class MiracleDonationTableRow():
    """Row in an island miracle donation table."""

    playerFlagTag: str
    playerName: str
    playerId: int
    playerCityName: str
    donated: int
    priests: int
    conversionPercent: float
    conversionIslandSharePercent: float


MiracleDontaionTableRow = MiracleDonationTableRow

@dataclass() 
class PlayerHighScoreTableRow():
    """Row in the player highscore table."""

    position: Optional[int]
    playerTitle: Optional[str]
    playerFlagTag: str
    playerName: str
    playerId: int
    isAlly: bool
    isVacation: bool
    isInactive: bool
    isBanned: bool
    playerAllianceTag: Optional[str]
    playerAllianceId: Optional[int]
    points: int

@dataclass()
class AllianceHighScoreTableRow():
    """Row in the alliance highscore table."""

    position: Optional[int]
    allianceFlagTag: str
    allianceName: Optional[str] # it's possible that an alliance has been deleted but is still in highscore
    allianceTag: str
    allianceId: int
    isAlly: bool
    members: int
    points: int
    averagePoints: int
    
class HighScoreTypes():
    """Valid ``highscoreType`` parameter values for player highscores."""

    totalScore = 'score'
    masterBuilder = 'building_score_main'
    buildingLevels = 'building_score_secondary'
    scientists = 'research_score_main'
    levelsOfResearch = 'research_score_secondary'
    generals = 'army_score_main'
    gold = 'trader_score_secondary'
    offensivePoints = 'offense'
    defencePoints = 'defense'
    trader = 'trade'
    resources = 'resources'
    donations = 'donations'
    pillaging = 'pillaging'
    capturePoints = 'piracy'


class AllianceHighScoreTypes():
    """Valid ``highscoreType`` parameter values for alliance highscores."""

    totalScore = 'score'
    averagePoints = 'avg_score'
    masterBuilder = 'buildingMainScore'
    buildingLevels = 'buildingSecondaryScore'
    scientists = 'researchMainScore'
    levelsOfResearch = 'researchSecondaryScore'
    generals = 'armyMainScore'
    gold = 'tradeSecondaryScore'
    offensivePoints = 'offenseScore'
    defencePoints = 'defenseScore'
    trader = 'tradeMainScore'
    resources = 'resourcesScore'
    donations = 'donationsScore'
    capturePoints = 'piracyScore'

class MayorMessageTypes():
    """Valid category filter names for mayor advisor messages."""

    military = 'military'
    transport = 'transport'
    production = 'production'
    espionage = 'espionage'
    diplomacy = 'diplomacy'
    plus = 'plus'
    piracy = 'piracy'


@dataclass
class MayorMessage():
    """Single message row in the mayor advisor overview."""

    type: str
    """Check data.MayorMessageTypes for valid strings"""
    isNew: bool
    cityName: str
    cityId: int
    date: datetime
    subjectHTML: str
    subject: str = ''

@dataclass
class MovementNode():
    """Origin or destination endpoint of a military or fleet movement."""

    cityName: str
    playerId: Optional[int]
    playerName: str
    cityId: Optional[int]
    islandId: Optional[int]

@dataclass
class MilitaryMovement():
    """Single active army or fleet movement entry from the military advisor."""

    movementId: int
    type: str
    missionId: int #various missions have different ids, 13 is for pillage
    missionText: str
    isReturning: bool
    isFleetReturning: bool
    isInFight: bool
    isCombatant: bool
    isOwnLoading: bool
    isLoadingAccelerated: bool
    canAbort: bool
    canRetreat: bool
    endTime: datetime
    isUnitsHidden: bool
    totalUnits: int
    units: List[Unit]
    totalTransportersAndFreighters: int
    totalResources: int
    resources: List[Resource]
    isOwnArmyOrFleet: bool
    isSameAlliance: bool
    isHostile: bool
    tritonEngines: bool
    origin: MovementNode
    target: MovementNode
    missionState: Optional[int] = None
    missionIconClass: str = ''
    eventDateText: str = ''
    targetHasBarbarianFleet: bool = False
    

    





