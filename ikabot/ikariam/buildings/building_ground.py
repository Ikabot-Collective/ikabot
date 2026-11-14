"""Model for an empty Ikariam construction ground (land or sea plot)."""

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_int,
    parse_query_int,
    parse_query_params,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_resources_ul,
    parse_view_payload,
)
from ikabot.ikariam.data import Resources

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


@dataclass
class BuildOption:
    """Represents a building type available to construct on a :class:`BuildingGround`."""

    buildingId: int
    buildingType: str
    name: str
    description: str
    cost: Resources
    missingResources: List[str]
    buildTimeSeconds: Optional[int]
    buildTimeBreakdown: Dict[str, str]
    canBuild: bool
    buildUrl: Optional[str]


class BuildingGround:
    """Empty building plot (``buildingGround land`` or ``buildingGround sea``) in a city."""

    client: Optional["Client"]
    city: Optional["City"]
    cityId: int
    position: int
    buildingId: None
    buildingType: str
    groundType: str
    name: str
    level: int
    groundId: int
    allowedBuildings: List[int]
    isLoaded: bool
    availableBuildings: List[BuildOption]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize an empty construction plot from city position metadata."""
        self.client = client
        self.city = city
        self.cityId = cityId if cityId else (city.id if city is not None else 0)
        self.position = position
        self.buildingId = None
        self.buildingType = "buildingGround"
        self.groundType = "land"
        self.name = "Building Ground"
        self.level = 0
        self.groundId = 0
        self.allowedBuildings = []
        self.isLoaded = False
        self.availableBuildings = []
        self._raw_position_data = data or {}
        if data:
            self._init_from_position_data(data)

    def _init_from_position_data(self, data: Dict[str, Any]) -> None:
        """Populate plot ground metadata from ``updateBackgroundData.position``."""
        self._raw_position_data = data
        raw = str(data.get("building") or "buildingGround land")
        self.buildingType = raw
        parts = raw.split()
        self.groundType = parts[1] if len(parts) > 1 else "land"
        self.groundId = parse_int(data.get("groundId")) or 0
        allowed = data.get("allowedBuildings")
        self.allowedBuildings = (
            [int(bid) for bid in allowed if parse_int(bid) is not None]
            if isinstance(allowed, list)
            else []
        )

    async def load(self) -> "BuildingGround":
        """Load the available construction options for this empty plot."""
        if self.client is None:
            raise RuntimeError("Cannot load buildingGround view without an attached Client")
        resp = await self.client.post_ajax(
            params={
                "view": "buildingGround",
                "cityId": str(self.cityId),
                "position": str(self.position),
                "backgroundView": "city",
                "currentCityId": str(self.cityId),
                "templateView": "buildingGround",
                "actionRequest": "REQUESTID",
            }
        )
        return self.parseView(resp)

    def parseView(self, viewData: Union[str, AjaxResponse]) -> "BuildingGround":
        """Parse ``view=buildingGround`` HTML or AJAX JSON into :attr:`availableBuildings`."""
        resp, soup = parse_view_payload(viewData)
        self.availableBuildings = []

        for li in soup.select("#buildings li.building"):
            classes = [c for c in (li.get("class") or []) if c != "building"]
            building_type = classes[0] if classes else ""

            headline = li.select_one("h4.headline")
            name = headline.get_text(" ", strip=True) if headline else building_type

            desc_p = li.find("p")
            description = desc_p.get_text(" ", strip=True) if desc_p else ""

            build_btn = li.find("a", class_="button") or li.find("a", href=True)
            build_url = str(build_btn["href"]) if build_btn and build_btn.get("href") else None
            building_id = parse_query_int(build_url, "building") if build_url else None

            if building_id is None:
                img_div = li.select_one(".buildingimg")
                onclick = str(img_div.get("onclick") or "") if img_div else ""
                m_bid = re.search(r"buildingId=(\d+)", onclick)
                if m_bid:
                    building_id = int(m_bid.group(1))

            if building_id is None:
                continue

            cost, missing, secs, breakdown = parse_resources_ul(li.select_one("ul.resources"))
            self.availableBuildings.append(
                BuildOption(
                    buildingId=building_id,
                    buildingType=building_type,
                    name=name,
                    description=description,
                    cost=cost,
                    missingResources=missing,
                    buildTimeSeconds=secs,
                    buildTimeBreakdown=breakdown,
                    canBuild=build_url is not None and not missing,
                    buildUrl=build_url,
                )
            )

        self.isLoaded = True
        return self

    async def build(self, buildingId: int) -> Building:
        """Construct a building with ``buildingId`` on this empty ground plot."""
        if self.client is None:
            raise RuntimeError("Cannot build without an attached Client")
        if not self.isLoaded:
            await self.load()

        option = next(
            (opt for opt in self.availableBuildings if opt.buildingId == buildingId),
            None,
        )
        if option is None:
            raise ValueError(
                f"Building ID {buildingId} is not available on ground {self.cityId}:{self.position}"
            )
        if not option.canBuild or not option.buildUrl:
            raise ValueError(
                f"Cannot build {option.name} (id={buildingId}) on {self.cityId}:{self.position}: "
                f"missing resources={option.missingResources}"
            )

        params = parse_query_params(option.buildUrl)
        params.setdefault("backgroundView", "city")
        params.setdefault("currentCityId", str(self.cityId))
        params.setdefault("templateView", "buildingGround")
        params["actionRequest"] = "REQUESTID"

        await self.client.post_action(
            params=params,
            metadata={"ambrosia_cost": 0},
            action_name="BuildingGround.build",
        )

        from ikabot.ikariam.buildings import BUILDING_CLASSES_BY_ID

        cls = BUILDING_CLASSES_BY_ID.get(buildingId, Building)
        building = cls(
            client=self.client,
            city=self.city,
            cityId=self.cityId,
            position=self.position,
        )
        if cls is Building:
            building.buildingId = buildingId
            building.buildingType = option.buildingType
        await building.load()
        return building
