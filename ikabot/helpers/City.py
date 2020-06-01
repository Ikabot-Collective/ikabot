# To use this code, make sure you
#
#     import json
#
# and then, to convert JSON from a string, do
#
#     result = Cityfromdict(json.loads(json_string))

from dataclasses import dataclass
from typing import Any, Optional, List, TypeVar, Type, cast, Callable


T = TypeVar("T")


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def from_bool(x: Any) -> bool:
    assert isinstance(x, bool)
    return x


def from_none(x: Any) -> Any:
    assert x is None
    return x


def from_union(fs, x):
    for f in fs:
        try:
            return f(x)
        except:
            pass
    assert False


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


@dataclass
class Visibility:
    military: int
    espionage: int
    resourceShop: int
    slot1: int
    slot2: int
    slot3: int
    slot4: int

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'Visibility':
        assert isinstance(obj, dict)
        military = from_int(obj.get("military"))
        espionage = from_int(obj.get("espionage"))
        resourceShop = from_int(obj.get("resourceShop"))
        slot1 = from_int(obj.get("slot1"))
        slot2 = from_int(obj.get("slot2"))
        slot3 = from_int(obj.get("slot3"))
        slot4 = from_int(obj.get("slot4"))
        return Visibility(military, espionage, resourceShop, slot1, slot2, slot3, slot4)

    def to_dict(self) -> dict:
        result: dict = {}
        result["military"] = from_int(self.military)
        result["espionage"] = from_int(self.espionage)
        result["resourceShop"] = from_int(self.resourceShop)
        result["slot1"] = from_int(self.slot1)
        result["slot2"] = from_int(self.slot2)
        result["slot3"] = from_int(self.slot3)
        result["slot4"] = from_int(self.slot4)
        return result


@dataclass
class CityLeftMenu:
    visibility: Visibility
    ownCity: int

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'CityLeftMenu':
        assert isinstance(obj, dict)
        visibility = Visibility.from_dict(obj.get("visibility"))
        ownCity = from_int(obj.get("ownCity"))
        return CityLeftMenu(visibility, ownCity)

    def to_dict(self) -> dict:
        result: dict = {}
        result["visibility"] = to_class(Visibility, self.visibility)
        result["ownCity"] = from_int(self.ownCity)
        return result


@dataclass
class Link:
    onclick: str
    href: str
    tooltip: str

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'Link':
        assert isinstance(obj, dict)
        onclick = from_str(obj.get("onclick"))
        href = from_str(obj.get("href"))
        tooltip = from_str(obj.get("tooltip"))
        return Link(onclick, href, tooltip)

    def to_dict(self) -> dict:
        result: dict = {}
        result["onclick"] = from_str(self.onclick)
        result["href"] = from_str(self.href)
        result["tooltip"] = from_str(self.tooltip)
        return result


@dataclass
class FlyingTrader:
    link: Link
    banner: str

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'FlyingTrader':
        assert isinstance(obj, dict)
        link = Link.from_dict(obj.get("link"))
        banner = from_str(obj.get("banner"))
        return FlyingTrader(link, banner)

    def to_dict(self) -> dict:
        result: dict = {}
        result["link"] = to_class(Link, self.link)
        result["banner"] = from_str(self.banner)
        return result


@dataclass
class Position:
    name: str
    isBusy: bool
    building: str
    position: int
    isMaxLevel: Optional[bool] = None
    canUpgrade: Optional[bool] = None
    level: Optional[str] = None
    type: Optional[str] = None

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'Position':
        assert isinstance(obj, dict)
        name = from_str(obj.get("name"))
        isBusy = from_bool(obj.get("isBusy"))
        building = from_str(obj.get("building"))
        position = from_int(obj.get("position"))
        level = from_union([from_str, from_none], obj.get("level"))
        canUpgrade = from_union([from_bool, from_none], obj.get("canUpgrade"))
        isMaxLevel = from_union([from_bool, from_none], obj.get("isMaxLevel"))
        type = from_union([from_str, from_none], obj.get("type"))
        return Position(name, isBusy, building, position, isMaxLevel, canUpgrade, level, type)

    def to_dict(self) -> dict:
        result: dict = {}
        result["name"] = from_str(self.name)
        result["isBusy"] = from_bool(self.isBusy)
        result["building"] = from_str(self.building)
        result["position"] = from_int(self.position)
        result["level"] = from_union([from_str, from_none], self.level)
        result["canUpgrade"] = from_union([from_bool, from_none], self.canUpgrade)
        result["isMaxLevel"] = from_union([from_bool, from_none], self.isMaxLevel)
        result["type"] = from_union([from_str, from_none], self.type)
        return result


@dataclass
class City:
    name: str
    id: str
    phase: int
    isCapital: bool
    islandId: str
    islandName: str
    buildingSpeedupActive: int
    showPirateFortressBackground: int
    showPirateFortressShip: int
    underConstruction: int
    endUpgradeTime: int
    startUpgradeTime: int
    position: List[Position]
    spiesInside: None
    cityLeftMenu: CityLeftMenu
    walkers: List[Any]
    displayStaticPlague: bool
    dailyTasks: str
    cityCinema: str
    flyingTrader: FlyingTrader
    Id: str
    Name: str
    x: str
    y: str
    cityName: str
    propia: bool
    recursos: List[int]
    capacidad: int
    ciudadanosDisp: int
    consumo: int
    enventa: List[int]
    freeSpaceForResources: List[int]

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'City':
        assert isinstance(obj, dict)
        name = from_str(obj.get("name"))
        id = from_str(obj.get("id"))
        phase = from_int(obj.get("phase"))
        isCapital = from_bool(obj.get("isCapital"))
        islandId = from_str(obj.get("islandId"))
        islandName = from_str(obj.get("islandName"))
        buildingSpeedupActive = from_int(obj.get("buildingSpeedupActive"))
        showPirateFortressBackground = from_int(obj.get("showPirateFortressBackground"))
        showPirateFortressShip = from_int(obj.get("showPirateFortressShip"))
        underConstruction = from_int(obj.get("underConstruction"))
        endUpgradeTime = from_int(obj.get("endUpgradeTime"))
        startUpgradeTime = from_int(obj.get("startUpgradeTime"))
        position = from_list(Position.from_dict, obj.get("position"))
        spiesInside = from_none(obj.get("spiesInside"))
        cityLeftMenu = CityLeftMenu.from_dict(obj.get("cityLeftMenu"))
        walkers = from_list(lambda x: x, obj.get("walkers"))
        displayStaticPlague = from_bool(obj.get("displayStaticPlague"))
        dailyTasks = from_str(obj.get("dailyTasks"))
        cityCinema = from_str(obj.get("cityCinema"))
        flyingTrader = FlyingTrader.from_dict(obj.get("flyingTrader"))
        Id = from_str(obj.get("Id"))
        Name = from_str(obj.get("Name"))
        x = from_str(obj.get("x"))
        y = from_str(obj.get("y"))
        cityName = from_str(obj.get("cityName"))
        propia = from_bool(obj.get("propia"))
        recursos = from_list(from_int, obj.get("recursos"))
        capacidad = from_int(obj.get("capacidad"))
        ciudadanosDisp = from_int(obj.get("ciudadanosDisp"))
        consumo = from_int(obj.get("consumo"))
        enventa = from_list(from_int, obj.get("enventa"))
        freeSpaceForResources = from_list(from_int, obj.get("freeSpaceForResources"))
        return City(name, id, phase, isCapital, islandId, islandName, buildingSpeedupActive, showPirateFortressBackground, showPirateFortressShip, underConstruction, endUpgradeTime, startUpgradeTime, position, spiesInside, cityLeftMenu, walkers, displayStaticPlague, dailyTasks, cityCinema, flyingTrader, Id, Name, x, y, cityName, propia, recursos, capacidad, ciudadanosDisp, consumo, enventa, freeSpaceForResources)

    def to_dict(self) -> dict:
        result: dict = {}
        result["name"] = from_str(self.name)
        result["id"] = from_str(self.id)
        result["phase"] = from_int(self.phase)
        result["isCapital"] = from_bool(self.isCapital)
        result["islandId"] = from_str(self.islandId)
        result["islandName"] = from_str(self.islandName)
        result["buildingSpeedupActive"] = from_int(self.buildingSpeedupActive)
        result["showPirateFortressBackground"] = from_int(self.showPirateFortressBackground)
        result["showPirateFortressShip"] = from_int(self.showPirateFortressShip)
        result["underConstruction"] = from_int(self.underConstruction)
        result["endUpgradeTime"] = from_int(self.endUpgradeTime)
        result["startUpgradeTime"] = from_int(self.startUpgradeTime)
        result["position"] = from_list(lambda x: to_class(Position, x), self.position)
        result["spiesInside"] = from_none(self.spiesInside)
        result["cityLeftMenu"] = to_class(CityLeftMenu, self.cityLeftMenu)
        result["walkers"] = from_list(lambda x: x, self.walkers)
        result["displayStaticPlague"] = from_bool(self.displayStaticPlague)
        result["dailyTasks"] = from_str(self.dailyTasks)
        result["cityCinema"] = from_str(self.cityCinema)
        result["flyingTrader"] = to_class(FlyingTrader, self.flyingTrader)
        result["Id"] = from_str(self.Id)
        result["Name"] = from_str(self.Name)
        result["x"] = from_str(self.x)
        result["y"] = from_str(self.y)
        result["cityName"] = from_str(self.cityName)
        result["propia"] = from_bool(self.propia)
        result["recursos"] = from_list(from_int, self.recursos)
        result["capacidad"] = from_int(self.capacidad)
        result["ciudadanosDisp"] = from_int(self.ciudadanosDisp)
        result["consumo"] = from_int(self.consumo)
        result["enventa"] = from_list(from_int, self.enventa)
        result["freeSpaceForResources"] = from_list(from_int, self.freeSpaceForResources)
        return result


def Cityfromdict(s: Any) -> City:
    return City.from_dict(s)


def Citytodict(x: City) -> Any:
    return to_class(City, x)
