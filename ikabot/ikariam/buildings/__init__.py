"""Ikariam building models and factory helpers."""

from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union

from ikabot.ikariam._parsing import parse_int
from ikabot.ikariam.buildings._base import Building
from ikabot.ikariam.buildings.academy import Academy
from ikabot.ikariam.buildings.alchemist import Alchemist
from ikabot.ikariam.buildings.architect import Architect
from ikabot.ikariam.buildings.barracks import Barracks
from ikabot.ikariam.buildings.black_market import BlackMarket
from ikabot.ikariam.buildings.branch_office import BranchOffice
from ikabot.ikariam.buildings.building_ground import BuildOption, BuildingGround
from ikabot.ikariam.buildings.carpentering import Carpentering
from ikabot.ikariam.buildings.chronos_forge import ChronosForge
from ikabot.ikariam.buildings.dockyard import Dockyard
from ikabot.ikariam.buildings.dump import Dump
from ikabot.ikariam.buildings.embassy import Embassy
from ikabot.ikariam.buildings.fireworker import Fireworker
from ikabot.ikariam.buildings.forester import Forester
from ikabot.ikariam.buildings.glassblowing import Glassblowing
from ikabot.ikariam.buildings.marine_chart_archive import MarineChartArchive
from ikabot.ikariam.buildings.museum import Museum
from ikabot.ikariam.buildings.optician import Optician
from ikabot.ikariam.buildings.palace import Palace
from ikabot.ikariam.buildings.palace_colony import PalaceColony
from ikabot.ikariam.buildings.pirate_fortress import PirateFortress
from ikabot.ikariam.buildings.port import Port
from ikabot.ikariam.buildings.safehouse import Safehouse
from ikabot.ikariam.buildings.shipyard import Shipyard
from ikabot.ikariam.buildings.shrine_of_olympus import ShrineOfOlympus
from ikabot.ikariam.buildings.stonemason import Stonemason
from ikabot.ikariam.buildings.tavern import Tavern
from ikabot.ikariam.buildings.temple import Temple
from ikabot.ikariam.buildings.town_hall import TownHall
from ikabot.ikariam.buildings.vineyard import Vineyard
from ikabot.ikariam.buildings.wall import Wall
from ikabot.ikariam.buildings.warehouse import Warehouse
from ikabot.ikariam.buildings.winegrower import Winegrower
from ikabot.ikariam.buildings.workshop import Workshop

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


BUILDING_CLASSES_BY_ID: Dict[int, Type[Building]] = {
    0: TownHall,
    3: Port,
    4: Academy,
    5: Shipyard,
    6: Barracks,
    7: Warehouse,
    8: Wall,
    9: Tavern,
    10: Museum,
    11: Palace,
    12: Embassy,
    13: BranchOffice,
    15: Workshop,
    16: Safehouse,
    17: PalaceColony,
    18: Forester,
    19: Stonemason,
    20: Glassblowing,
    21: Winegrower,
    22: Alchemist,
    23: Carpentering,
    24: Architect,
    25: Optician,
    26: Vineyard,
    27: Fireworker,
    28: Temple,
    29: Dump,
    30: PirateFortress,
    31: BlackMarket,
    32: MarineChartArchive,
    33: Dockyard,
    34: ShrineOfOlympus,
    35: ChronosForge,
}

BUILDING_CLASSES_BY_TYPE: Dict[str, Type[Building]] = {
    "townHall": TownHall,
    "port": Port,
    "academy": Academy,
    "shipyard": Shipyard,
    "barracks": Barracks,
    "warehouse": Warehouse,
    "wall": Wall,
    "tavern": Tavern,
    "museum": Museum,
    "palace": Palace,
    "embassy": Embassy,
    "branchOffice": BranchOffice,
    "workshop": Workshop,
    "safehouse": Safehouse,
    "palaceColony": PalaceColony,
    "forester": Forester,
    "stonemason": Stonemason,
    "glassblowing": Glassblowing,
    "winegrower": Winegrower,
    "alchemist": Alchemist,
    "carpentering": Carpentering,
    "architect": Architect,
    "optician": Optician,
    "vineyard": Vineyard,
    "fireworker": Fireworker,
    "temple": Temple,
    "dump": Dump,
    "pirateFortress": PirateFortress,
    "blackMarket": BlackMarket,
    "marineChartArchive": MarineChartArchive,
    "dockyard": Dockyard,
    "shrineOfOlympus": ShrineOfOlympus,
    "chronosForge": ChronosForge,
}


def createBuilding(
    data: Optional[Dict[str, Any]],
    *,
    client: Optional["Client"] = None,
    city: Optional["City"] = None,
    cityId: int = 0,
    position: int = 0,
) -> Optional[Union[Building, BuildingGround]]:
    """Instantiate the appropriate building model or :class:`BuildingGround` from a city plot dict."""
    if not isinstance(data, dict):
        return None
    raw_building = str(data.get("building") or "").strip()
    if not raw_building or raw_building == "empty":
        return None
    if raw_building.startswith("buildingGround"):
        return BuildingGround(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )

    building_id = parse_int(data.get("buildingId"))
    building_type = raw_building.split()[0]
    cls = (
        BUILDING_CLASSES_BY_ID.get(building_id)
        if building_id is not None
        else None
    ) or BUILDING_CLASSES_BY_TYPE.get(building_type, Building)

    return cls(
        client=client,
        city=city,
        cityId=cityId,
        position=position,
        data=data,
    )


__all__ = [
    "Academy",
    "Alchemist",
    "Architect",
    "BUILDING_CLASSES_BY_ID",
    "BUILDING_CLASSES_BY_TYPE",
    "Barracks",
    "BlackMarket",
    "BranchOffice",
    "BuildOption",
    "Building",
    "BuildingGround",
    "Carpentering",
    "ChronosForge",
    "Dockyard",
    "Dump",
    "Embassy",
    "Fireworker",
    "Forester",
    "Glassblowing",
    "MarineChartArchive",
    "Museum",
    "Optician",
    "Palace",
    "PalaceColony",
    "PirateFortress",
    "Port",
    "Safehouse",
    "Shipyard",
    "ShrineOfOlympus",
    "Stonemason",
    "Tavern",
    "Temple",
    "TownHall",
    "Vineyard",
    "Wall",
    "Warehouse",
    "Winegrower",
    "Workshop",
    "createBuilding",
]
