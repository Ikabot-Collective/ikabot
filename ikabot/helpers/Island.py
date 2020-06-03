# To use this code, make sure you
#
#     import json
#
# and then, to convert JSON from a string, do
#
#     result = Islandfromdict(json.loads(json_string))

from dataclasses import dataclass
from typing import Any, Optional, List, Dict, TypeVar, Callable, Type, cast


T = TypeVar("T")


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def from_str(x: Any) -> str:
    assert isinstance(x, str)
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


def from_bool(x: Any) -> bool:
    assert isinstance(x, bool)
    return x


def from_dict(f: Callable[[Any], T], x: Any) -> Dict[str, T]:
    assert isinstance(x, dict)
    return { k: f(v) for (k, v) in x.items() }


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@dataclass
class Barbarians:
    invisible: int
    actionTitle: str
    actionClass: str
    actionLink: str
    count: int
    wallLevel: int
    level: int
    underAttack: int
    isTradegoodSiege: int
    city: Optional[str] = None #these will be none if the barbarians aren't on your island
    destroyed: Optional[int] = None #these will be none if the barbarians aren't on your island

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'Barbarians':
        assert isinstance(obj, dict)
        invisible = from_int(obj.get("invisible"))
        actionTitle = from_str(obj.get("actionTitle"))
        actionClass = from_str(obj.get("actionClass"))
        actionLink = from_str(obj.get("actionLink"))
        count = from_int(obj.get("count"))
        wallLevel = from_int(obj.get("wallLevel"))
        level = from_int(obj.get("level"))
        underAttack = from_int(obj.get("underAttack"))
        isTradegoodSiege = from_int(obj.get("isTradegoodSiege"))
        city = from_union([from_str, from_none], obj.get("city"))
        destroyed = from_union([from_int, from_none], obj.get("destroyed"))
        return Barbarians(invisible, actionTitle, actionClass, actionLink, count, wallLevel, level, underAttack, isTradegoodSiege, city, destroyed)

    def to_dict(self) -> dict:
        result: dict = {}
        result["invisible"] = from_int(self.invisible)
        result["actionTitle"] = from_str(self.actionTitle)
        result["actionClass"] = from_str(self.actionClass)
        result["actionLink"] = from_str(self.actionLink)
        result["count"] = from_int(self.count)
        result["wallLevel"] = from_int(self.wallLevel)
        result["level"] = from_int(self.level)
        result["underAttack"] = from_int(self.underAttack)
        result["isTradegoodSiege"] = from_int(self.isTradegoodSiege)
        result["city"] = from_str(self.city)
        result["destroyed"] = from_int(self.destroyed)
        return result


@dataclass
class IslandCity:
    type: str
    name: Optional[str] = None
    id: Optional[int] = None
    level: Optional[str] = None
    Id: Optional[str] = None
    Name: Optional[str] = None
    AllyId: Optional[str] = None
    AllyTag: Optional[str] = None
    actions: Optional[List[Any]] = None #won't be empty if you can do piracy raid
    state: Optional[str] = None

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'City':
        assert isinstance(obj, dict)
        type = from_str(obj.get("type"))
        name = from_union([from_str, from_none], obj.get("name"))
        id = from_union([from_int, from_none], obj.get("id"))
        level = from_union([from_str, from_none], obj.get("level"))
        Id = from_union([from_str, from_none], obj.get("Id"))
        Name = from_union([from_str, from_none], obj.get("Name"))
        AllyId = from_union([from_str, from_none], obj.get("AllyId"))
        AllyTag = from_union([from_str, from_none], obj.get("AllyTag"))
        actions = from_union([lambda x: from_list(lambda x: x, x), from_none], obj.get("actions"))
        state = from_union([from_str, from_none], obj.get("state"))
        return IslandCity(type, name, id, level, Id, Name, AllyId, AllyTag, actions, state)

    def to_dict(self) -> dict:
        result: dict = {}
        result["type"] = from_str(self.type)
        result["name"] = from_union([from_str, from_none], self.name)
        result["id"] = from_union([from_int, from_none], self.id)
        result["level"] = from_union([from_str, from_none], self.level)
        result["Id"] = from_union([from_str, from_none], self.Id)
        result["Name"] = from_union([from_str, from_none], self.Name)
        result["AllyId"] = from_union([from_str, from_none], self.AllyId)
        result["AllyTag"] = from_union([from_str, from_none], self.AllyTag)
        result["actions"] = from_union([lambda x: from_list(lambda x: x, x), from_none], self.actions)
        result["state"] = from_union([from_str, from_none], self.state)
        return result


@dataclass
class Score:
    avatarid: str
    place: str
    buildingscoremain: str
    researchscoremain: str
    armyscoremain: str
    traderscoresecondary: str

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'Score':
        assert isinstance(obj, dict)
        avatarid = from_str(obj.get("avatar_id"))
        place = from_str(obj.get("place"))
        buildingscoremain = from_str(obj.get("building_score_main"))
        researchscoremain = from_str(obj.get("research_score_main"))
        armyscoremain = from_str(obj.get("army_score_main"))
        traderscoresecondary = from_str(obj.get("trader_score_secondary"))
        return Score(avatarid, place, buildingscoremain, researchscoremain, armyscoremain, traderscoresecondary)

    def to_dict(self) -> dict:
        result: dict = {}
        result["avatar_id"] = from_str(self.avatarid)
        result["place"] = from_str(self.place)
        result["building_score_main"] = from_str(self.buildingscoremain)
        result["research_score_main"] = from_str(self.researchscoremain)
        result["army_score_main"] = from_str(self.armyscoremain)
        result["trader_score_secondary"] = from_str(self.traderscoresecondary)
        return result


@dataclass
class Island:
    id: str
    name: str
    x: str
    y: str
    good: str
    woodLv: str
    goodLv: str
    wonder: str
    wonderLv: str
    wonderName: str
    showResourceWorkers: int
    showTradegoodWorkers: int
    showAgora: int
    canEnterResource: int
    canEnterTradegood: int
    goodEndUpgradeTime: int
    resourceEndUpgradeTime: int
    wonderEndUpgradeTime: int
    isOwnCityOnIsland: bool
    cities: List[IslandCity]
    barbarians: Barbarians
    scores: Dict[str, Score]

    def __getitem__(self,key):
        return getattr(self,key)
    
    def __setitem__(self,key,newvalue):
        setattr(self,key,newvalue)

    @staticmethod
    def from_dict(obj: Any) -> 'Island':
        assert isinstance(obj, dict)
        id = from_str(obj.get("id"))
        name = from_str(obj.get("name"))
        x = from_str(obj.get("x"))
        y = from_str(obj.get("y"))
        good = from_str(obj.get("good"))
        woodLv = from_str(obj.get("woodLv"))
        goodLv = from_str(obj.get("goodLv"))
        wonder = from_str(obj.get("wonder"))
        wonderLv = from_str(obj.get("wonderLv"))
        wonderName = from_str(obj.get("wonderName"))
        showResourceWorkers = from_int(obj.get("showResourceWorkers"))
        showTradegoodWorkers = from_int(obj.get("showTradegoodWorkers"))
        showAgora = from_int(obj.get("showAgora"))
        canEnterResource = from_int(obj.get("canEnterResource"))
        canEnterTradegood = from_int(obj.get("canEnterTradegood"))
        goodEndUpgradeTime = from_int(obj.get("goodEndUpgradeTime"))
        resourceEndUpgradeTime = from_int(obj.get("resourceEndUpgradeTime"))
        wonderEndUpgradeTime = from_int(obj.get("wonderEndUpgradeTime"))
        isOwnCityOnIsland = from_bool(obj.get("isOwnCityOnIsland"))
        cities = from_list(IslandCity.from_dict, obj.get("cities"))
        barbarians = Barbarians.from_dict(obj.get("barbarians"))
        scores = from_dict(Score.from_dict, obj.get("scores"))
        return Island(id, name, x, y, good, woodLv, goodLv, wonder, wonderLv, wonderName, showResourceWorkers, showTradegoodWorkers, showAgora, canEnterResource, canEnterTradegood, goodEndUpgradeTime, resourceEndUpgradeTime, wonderEndUpgradeTime, isOwnCityOnIsland, cities, barbarians, scores)

    def to_dict(self) -> dict:
        result: dict = {}
        result["id"] = from_str(self.id)
        result["name"] = from_str(self.name)
        result["x"] = from_str(self.x)
        result["y"] = from_str(self.y)
        result["good"] = from_str(self.good)
        result["woodLv"] = from_str(self.woodLv)
        result["goodLv"] = from_str(self.goodLv)
        result["wonder"] = from_str(self.wonder)
        result["wonderLv"] = from_str(self.wonderLv)
        result["wonderName"] = from_str(self.wonderName)
        result["showResourceWorkers"] = from_int(self.showResourceWorkers)
        result["showTradegoodWorkers"] = from_int(self.showTradegoodWorkers)
        result["showAgora"] = from_int(self.showAgora)
        result["canEnterResource"] = from_int(self.canEnterResource)
        result["canEnterTradegood"] = from_int(self.canEnterTradegood)
        result["goodEndUpgradeTime"] = from_int(self.goodEndUpgradeTime)
        result["resourceEndUpgradeTime"] = from_int(self.resourceEndUpgradeTime)
        result["wonderEndUpgradeTime"] = from_int(self.wonderEndUpgradeTime)
        result["isOwnCityOnIsland"] = from_bool(self.isOwnCityOnIsland)
        result["cities"] = from_list(lambda x: to_class(IslandCity, x), self.cities)
        result["barbarians"] = to_class(Barbarians, self.barbarians)
        result["scores"] = from_dict(lambda x: to_class(Score, x), self.scores)
        return result


def Islandfromdict(s: Any) -> Island:
    return Island.from_dict(s)


def Islandtodict(x: Island) -> Any:
    return to_class(Island, x)
