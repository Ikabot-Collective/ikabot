"""Ikariam city models and mission/action views."""

from datetime import datetime
import json
import math
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Type, TypeVar, Union

from bs4 import BeautifulSoup, Tag

from ikabot.config import materials_names_english
from ikabot.ikariam._parsing import (
    AjaxResponse,
    decode_unicode_escape,
    extract_ajax_responder,
    extract_js_json_parse,
    extract_js_object,
    make_soup,
    parse_ajax_response,
    parse_float,
    parse_int,
    parse_query_params,
    parse_query_str,
)
from ikabot.ikariam.buildings import (
    BUILDING_CLASSES_BY_ID,
    BUILDING_CLASSES_BY_TYPE,
    Building,
    BuildingGround,
    createBuilding,
)
from ikabot.ikariam.buildings._base import (
    parse_duration_seconds,
    parse_view_payload,
    tmpl_int,
    tmpl_text,
)
from ikabot.ikariam.data import PlayerHighScoreTableRow, Resource, Resources, Unit, Units
from ikabot.ikariam.player import AvatarScore

if TYPE_CHECKING:
    from ikabot.ikariam.client import Client
    from ikabot.ikariam.island import Island

TBuilding = TypeVar("TBuilding", bound=Building)


_ACTION_HREF_FLAGS = (
    ("sendIKMessage", "canDiplomacy"),
    ("transport", "canTransportGoods"),
    ("defendCity", "canDefendCity"),
    ("defendPort", "canDefendPort"),
    ("plunder", "canPillage"),
    ("blockade", "canOccupyPort"),
    ("occupy", "canOccupyCity"),
    ("sendSpy", "canSendSpy"),
)


def _extract_js_number(block: str, key: str) -> Optional[str]:
    """Extract a numeric value string for ``key`` from a JavaScript object literal."""
    match = re.search(
        rf"""['"]?{re.escape(key)}['"]?\s*:\s*['"]?(-?\d+(?:\.\d+)?)['"]?""",
        block,
    )
    return match.group(1) if match else None


def _extract_alliance_tag(text: str) -> Optional[str]:
    """Extract a bracketed alliance tag from an occupier label or tooltip."""
    if "[" not in text:
        return None
    tag = text.split("[", 1)[1].split("]", 1)[0].strip()
    return tag or None


def _extract_view_html(viewData: str) -> str:
    """Return raw view HTML whether ``viewData`` is HTML or an ``ajax=1`` JSON payload."""
    if viewData.lstrip().startswith("["):
        return parse_ajax_response(viewData).view_html or ""
    return viewData


class City:
    """Full representation of an Ikariam city loaded from ``view=city``."""

    id: int
    name: str
    ownerId: int
    ownerName: str
    islandId: int
    islandName: str
    x: int
    y: int
    isCapital: bool
    spiesInside: int
    underConstruction: Any
    positions: list
    plots: List[Optional[Union[Building, BuildingGround]]]
    buildings: List[Building]
    buildingGrounds: List[BuildingGround]
    ambrosiaFountainStatus: Optional[str]
    hasAmbrosiaFountain: bool
    isAmbrosiaFountainActive: bool
    cinemaStatus: Optional[str]
    dailyTasksCount: Optional[int]
    flyingTrader: Optional[Dict[str, Any]]
    shopHref: Optional[str]
    client: Optional["Client"]

    def __init__(self, client: Optional["Client"], data: dict) -> None:
        """Initialize a city and typed building plots from ``ajax.Responder`` ``updateBackgroundData``."""
        self.client = client
        self.id = parse_int(data.get("id")) or 0
        self.name = decode_unicode_escape(data.get("name"))
        self.ownerId = parse_int(data.get("ownerId")) or 0
        self.ownerName = decode_unicode_escape(data.get("ownerName"))
        self.islandId = parse_int(data.get("islandId")) or 0
        self.islandName = decode_unicode_escape(data.get("islandName"))
        self.x = parse_int(data.get("islandXCoord", data.get("xCoord"))) or 0
        self.y = parse_int(data.get("islandYCoord", data.get("yCoord"))) or 0
        self.isCapital = bool(data.get("isCapital", False))
        self.spiesInside = parse_int(data.get("spiesInside")) or 0
        self.underConstruction = data.get("underConstruction")
        positions = data.get("position", [])
        self.positions = positions if isinstance(positions, list) else []
        self.plots = []
        self.buildings = []
        self.buildingGrounds = []
        for idx, pos_data in enumerate(self.positions):
            plot = createBuilding(
                pos_data,
                client=client,
                city=self,
                cityId=self.id,
                position=idx,
            )
            self.plots.append(plot)
            if isinstance(plot, BuildingGround):
                self.buildingGrounds.append(plot)
            elif isinstance(plot, Building):
                self.buildings.append(plot)
        raw_fountain = data.get("ambrosiaFountain")
        self.ambrosiaFountainStatus = str(raw_fountain) if raw_fountain is not None else None
        # Divine Ambrosia Fountain only exists in the player's capital city.
        self.hasAmbrosiaFountain = self.ambrosiaFountainStatus is not None
        self.isAmbrosiaFountainActive = self.ambrosiaFountainStatus == "fountain_active"

        raw_cinema = data.get("cityCinema")
        self.cinemaStatus = str(raw_cinema) if raw_cinema is not None else None
        self.dailyTasksCount = parse_int(data.get("dailyTasks"))

        raw_trader = data.get("flyingTrader")
        self.flyingTrader = raw_trader if isinstance(raw_trader, dict) else None
        trader_link = (
            self.flyingTrader.get("link")
            if isinstance(self.flyingTrader, dict)
            else None
        )
        self.shopHref = (
            str(trader_link.get("href"))
            if isinstance(trader_link, dict) and trader_link.get("href")
            else None
        )
        self.__city_data = data

    async def _fetch_city_view(
        self,
        view: str,
        *,
        activeTab: Optional[str] = None,
        extraParams: Optional[Dict[str, str]] = None,
    ) -> AjaxResponse:
        """Fetch an AJAX view anchored on this city (read-only)."""
        if self.client is None:
            raise ValueError("City is not bound to an active Client")
        params: Dict[str, str] = {
            "view": view,
            "cityId": str(self.id),
            "backgroundView": "city",
            "currentCityId": str(self.id),
            "templateView": view,
            "actionRequest": "REQUESTID",
            "ajax": "1",
        }
        if activeTab:
            params["activeTab"] = activeTab
        if extraParams:
            params.update(extraParams)
        resp = await self.client.post_ajax(params=params)
        if not resp.view_html:
            feedback = "; ".join(
                str(item.get("text", ""))
                for item in resp.feedback
                if isinstance(item, dict) and item.get("text")
            )
            detail = f": {feedback}" if feedback else ""
            raise ValueError(f"Could not open {view!r} view for city {self.id}{detail}")
        return resp

    async def getDailyTasks(self, includeRewards: bool = False) -> "DailyTasksView":
        """Open the Daily Tasks popup view for this city (read-only)."""
        tasks_resp = await self._fetch_city_view("dailyTasks")
        rewards_resp = (
            await self._fetch_city_view("dailyTasksRewards", activeTab="tab_dailyTasksRewards")
            if includeRewards
            else None
        )
        return DailyTasksView(tasks_resp, rewardsViewData=rewards_resp, city=self)

    async def getDailyTasksRewards(self) -> List["DailyTaskRewardEntry"]:
        """Open the Daily Tasks Rewards tab and return redeemable favor rewards."""
        rewards_resp = await self._fetch_city_view(
            "dailyTasksRewards",
            activeTab="tab_dailyTasksRewards",
        )
        return DailyTasksView(rewards_resp, city=self).rewards

    async def getCinema(self) -> "CinemaView":
        """Open the Cinetheatre popup view for this city (read-only)."""
        resp = await self._fetch_city_view("cinema", extraParams={"visit": "1"})
        return CinemaView(resp, city=self)

    async def getAmbrosiaFountain(self) -> Optional["AmbrosiaFountainView"]:
        """Open the Divine Ambrosia Fountain view if present in this city (capital only)."""
        if not self.hasAmbrosiaFountain:
            return None
        resp = await self._fetch_city_view("ambrosiaFountain")
        return AmbrosiaFountainView(resp, city=self)

    async def getShop(self) -> "ShopView":
        """Open the Flying Trader / Shop view for this city (read-only)."""
        link_type = parse_query_str(self.shopHref or "", "linkType") or "3"
        resp = await self._fetch_city_view("premium", extraParams={"linkType": link_type})
        return ShopView(resp, city=self, shopHref=self.shopHref)

    async def collectDailyActivityBonus(self) -> AjaxResponse:
        """Collect the 7-day daily login wine bonus into this city."""
        if self.client is None:
            raise ValueError("City is not bound to an active Client")
        return await self.client.post_action(
            payloadPost={
                "action": "AvatarAction",
                "function": "giveDailyActivityBonus",
                "dailyActivityBonusCitySelect": str(self.id),
            },
            params={
                "backgroundView": "city",
                "currentCityId": str(self.id),
                "actionRequest": "REQUESTID",
            },
            metadata={"cityId": self.id, "ambrosia_cost": 0},
            action_name="City.collectDailyActivityBonus",
        )

    async def _ensure_selected(self) -> None:
        """Ensure this city is the active session city before opening origin-scoped views."""
        if self.client is None:
            raise ValueError("City is not bound to an active Client")
        await _select_city_id(self.client, self.id, action_name="City._ensure_selected")

    async def transportGoods(self, destinationCityId: int) -> "TransportView":
        """Open the goods transport view from this city to ``destinationCityId``."""
        await self._ensure_selected()
        resp = await self._fetch_city_view(
            "transport",
            extraParams={"destinationCityId": str(int(destinationCityId))},
        )
        return TransportView(resp.view_html or "", client=self.client, originCityId=self.id)

    async def _open_deployment_view(
        self,
        destinationCityId: int,
        deploymentType: str,
    ) -> "SendUnitsView":
        """Open an army or fleet deployment screen from this city to ``destinationCityId``."""
        await self._ensure_selected()
        resp = await self._fetch_city_view(
            "deployment",
            extraParams={
                "deploymentType": deploymentType,
                "destinationCityId": str(int(destinationCityId)),
            },
        )
        return SendUnitsView(resp.view_html or "", client=self.client, originCityId=self.id)

    async def deployArmy(self, destinationCityId: int) -> "SendUnitsView":
        """Open the army deployment view from this city to ``destinationCityId``."""
        return await self._open_deployment_view(destinationCityId, "army")

    async def deployFleet(self, destinationCityId: int) -> "SendUnitsView":
        """Open the fleet deployment view from this city to ``destinationCityId``."""
        return await self._open_deployment_view(destinationCityId, "fleet")

    def getBuilding(
        self, buildingTypeOrId: Union[str, int, Type[TBuilding]]
    ) -> Optional[Union[Building, TBuilding]]:
        """Return the first matching building in this city by class, type key, or building ID."""
        matches = self.getBuildings(buildingTypeOrId)
        return matches[0] if matches else None

    def getBuildings(
        self, buildingTypeOrId: Union[str, int, Type[TBuilding]]
    ) -> List[Any]:
        """Return all matching buildings in this city by class, type key, or building ID."""
        if isinstance(buildingTypeOrId, type) and issubclass(buildingTypeOrId, Building):
            return [b for b in self.buildings if isinstance(b, buildingTypeOrId)]
        if isinstance(buildingTypeOrId, int) and not isinstance(buildingTypeOrId, bool):
            target_cls = BUILDING_CLASSES_BY_ID.get(buildingTypeOrId)
            return [
                b
                for b in self.buildings
                if b.buildingId == buildingTypeOrId
                or (target_cls is not None and isinstance(b, target_cls))
            ]
        key = str(buildingTypeOrId).split()[0]
        target_cls = BUILDING_CLASSES_BY_TYPE.get(key)
        return [
            b
            for b in self.buildings
            if b.buildingType == key
            or (target_cls is not None and isinstance(b, target_cls))
        ]

    def getBuildingAt(
        self, position: int
    ) -> Optional[Union[Building, BuildingGround]]:
        """Return the building or empty ground plot at city ``position`` index."""
        if 0 <= position < len(self.plots):
            return self.plots[position]
        return None


class DropdownCity:
    """City summary gathered from the header city dropdown menu.

    ``luxuryResourceType`` and ``luxuryResourceName`` are ``None`` when the city
    is not owned by the current player.
    """

    id: int
    x: int
    y: int
    name: str
    luxuryResourceType: Optional[int]
    luxuryResourceName: Optional[str]
    isOwnCity: bool

    def __init__(self, client: "Client", dropdownCity: dict) -> None:
        """Initialize a dropdown city entry from ``relatedCityData``."""
        self._client = client
        self.id = parse_int(dropdownCity.get("id")) or 0
        coords_raw = str(dropdownCity.get("coords") or "").strip().strip("[]")
        x_part, _, y_part = coords_raw.partition(":")
        self.x = parse_int(x_part) or 0
        self.y = parse_int(y_part) or 0
        self.name = decode_unicode_escape(dropdownCity.get("name"))
        self.isOwnCity = dropdownCity.get("relationship") == "ownCity"
        if self.isOwnCity:
            tradegood = parse_int(dropdownCity.get("tradegood"))
            self.luxuryResourceType = tradegood
            self.luxuryResourceName = (
                materials_names_english[tradegood]
                if tradegood is not None and 0 <= tradegood < len(materials_names_english)
                else None
            )
        else:
            self.luxuryResourceType = None
            self.luxuryResourceName = None

    async def getCity(self) -> City:
        """Send a request to obtain full data about this city."""
        html = await self._client.get(f"view=city&cityId={self.id}")
        commands = html if html.lstrip().startswith("[") else extract_ajax_responder(html)
        resp = parse_ajax_response(commands)
        if not resp.background_data:
            raise ValueError(f"Could not find updateBackgroundData for city {self.id}")
        return City(self._client, resp.background_data)

    async def selectCity(self) -> Optional[City]:
        """Select this dropdown city as the active city and return its refreshed :class:`City`."""
        if not self.isOwnCity:
            return None
        resp = await _select_city_id(
            self._client,
            self.id,
            force=True,
            action_name="DropdownCity.selectCity",
        )
        if resp is not None and resp.background_data:
            return City(self._client, resp.background_data)
        return await self.getCity()


async def _select_city_id(
    client: "Client",
    city_id: int,
    *,
    force: bool = False,
    action_name: str = "_select_city_id",
) -> Optional[AjaxResponse]:
    """Ensure ``city_id`` is the server-side active city via ``changeCurrentCity``."""
    selected = client.selectedDropDownCity
    if not force and selected is not None and selected.id == city_id:
        return None
    current_id = selected.id if selected is not None else city_id
    return await client.post_action(
        params={
            "action": "header",
            "function": "changeCurrentCity",
            "cityId": str(city_id),
            "oldView": "city",
            "backgroundView": "city",
            "currentCityId": str(current_id),
            "actionRequest": "REQUESTID",
        },
        metadata={"cityId": city_id, "ambrosia_cost": 0},
        action_name=action_name,
    )


def _collect_form_inputs(form: Tag) -> Dict[str, str]:
    """Extract default non-submit named ``<input>`` field values from an HTML ``<form>``."""
    fields: Dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        inp_type = str(inp.get("type") or "").lower()
        if inp_type in ("submit", "button", "image", "reset"):
            continue
        if name == "actionRequest":
            continue
        fields[str(name)] = str(inp.get("value") or "")
    return fields


def _normalize_resource_amounts(
    resources: Optional[Union[Resources, Sequence[Resource], Dict[str, int]]],
    *,
    wood: int = 0,
    wine: int = 0,
    marble: int = 0,
    crystal: int = 0,
    sulphur: int = 0,
) -> Dict[str, int]:
    """Normalize resource inputs into Ikariam ``cargo_*`` transport form field counts."""
    counts = {
        "cargo_resource": int(wood),
        "cargo_tradegood1": int(wine),
        "cargo_tradegood2": int(marble),
        "cargo_tradegood3": int(crystal),
        "cargo_tradegood4": int(sulphur),
    }
    key_map = {
        "wood": "cargo_resource",
        "resource": "cargo_resource",
        "wine": "cargo_tradegood1",
        "tradegood1": "cargo_tradegood1",
        "marble": "cargo_tradegood2",
        "tradegood2": "cargo_tradegood2",
        "crystal": "cargo_tradegood3",
        "glass": "cargo_tradegood3",
        "tradegood3": "cargo_tradegood3",
        "sulphur": "cargo_tradegood4",
        "sulfur": "cargo_tradegood4",
        "tradegood4": "cargo_tradegood4",
    }
    if isinstance(resources, Resources):
        counts["cargo_resource"] += resources.Wood.count
        counts["cargo_tradegood1"] += resources.Wine.count
        counts["cargo_tradegood2"] += resources.Marble.count
        counts["cargo_tradegood3"] += resources.Crystal.count
        counts["cargo_tradegood4"] += resources.Sulphur.count
    elif isinstance(resources, dict):
        for raw_k, raw_v in resources.items():
            target_key = key_map.get(str(raw_k).strip().lower())
            if target_key is None:
                raise ValueError(f"Unsupported transport resource key: {raw_k!r}")
            counts[target_key] += int(raw_v)
    elif resources is not None:
        for res in resources:
            if not isinstance(res, Resource):
                raise ValueError(f"Expected Resource item, got {type(res).__name__}")
            target_key = key_map.get(res.cssClass.lower()) or key_map.get(res.name.lower())
            if target_key is None:
                raise ValueError(f"Unsupported transport Resource type: {res.name!r}")
            counts[target_key] += int(res.count)

    for k, v in counts.items():
        if v < 0:
            raise ValueError(f"Transport resource amount cannot be negative ({k}={v})")
    if sum(counts.values()) <= 0:
        raise ValueError("Must specify a positive quantity of at least one resource to transport")
    return counts


def _normalize_unit_counts(
    units: Union[
        Sequence[Unit],
        Dict[Union[int, str, Unit], int],
        Sequence[Tuple[Union[int, str, Unit], int]],
    ],
    available_units: Sequence[Unit] = (),
) -> Dict[int, int]:
    """Normalize requested unit/ship counts into ``{unit_id: count}``."""
    requested: Dict[int, int] = {}
    items = list(units.items()) if isinstance(units, dict) else list(units)
    for item in items:
        if isinstance(item, Unit):
            uid, count = item.id, int(item.count)
        elif isinstance(item, tuple) and len(item) == 2:
            raw_u, raw_c = item
            count = int(raw_c)
            if isinstance(raw_u, Unit):
                uid = raw_u.id
            elif isinstance(raw_u, int) and not isinstance(raw_u, bool):
                uid = raw_u
            else:
                parsed_id = parse_int(str(raw_u))
                if parsed_id is not None and str(parsed_id) == str(raw_u).strip():
                    uid = parsed_id
                else:
                    needle = str(raw_u).strip().lower().replace("_", " ")
                    match = next(
                        (
                            u
                            for u in available_units
                            if u.name.lower().replace("_", " ") == needle
                        ),
                        None,
                    )
                    if match is None:
                        raise ValueError(f"Unknown unit specifier: {raw_u!r}")
                    uid = match.id
        else:
            raise ValueError(f"Unsupported unit entry: {item!r}")

        if count < 0:
            raise ValueError(f"Unit count cannot be negative (unitId={uid}, count={count})")
        if count > 0:
            requested[uid] = requested.get(uid, 0) + count

    if not requested:
        raise ValueError("Must specify at least one unit or ship with count > 0")
    return requested


async def _submit_unit_mission_form(
    client: "Client",
    view_html: str,
    units: Union[
        Sequence[Unit],
        Dict[Union[int, str, Unit], int],
        Sequence[Tuple[Union[int, str, Unit], int]],
    ],
    *,
    transporters: Optional[int] = None,
    available_units: Sequence[Unit] = (),
    origin_city_id: Optional[int] = None,
    action_name: str,
) -> AjaxResponse:
    """Populate and submit a mission deployment or pillage ``<form>``."""
    soup = make_soup(view_html)
    form = (
        soup.select_one("#plunderForm, #armyDeploymentForm, #fleetDeploymentForm")
        or soup.find("form")
    )
    if form is None:
        raise ValueError(f"Could not find mission deployment form in {action_name}")

    payload = _collect_form_inputs(form)
    requested = _normalize_unit_counts(units, available_units=available_units)
    avail_by_id = {u.id: u.count for u in available_units}

    sent_total = 0
    for uid, count in requested.items():
        if uid in avail_by_id and count > avail_by_id[uid]:
            raise ValueError(
                f"Requested {count} of unit {uid}, but only {avail_by_id[uid]} available"
            )
        fleet_key = f"cargo_fleet_{uid}"
        army_key = f"cargo_army_{uid}"
        if fleet_key in payload:
            payload[fleet_key] = str(count)
        elif army_key in payload:
            payload[army_key] = str(count)
        elif any(k.startswith("cargo_fleet_") for k in payload):
            payload[fleet_key] = str(count)
        else:
            payload[army_key] = str(count)
        sent_total += count

    if sent_total <= 0:
        raise ValueError("Must send at least one unit")

    if transporters is not None:
        if transporters < 0:
            raise ValueError(f"transporters cannot be negative ({transporters})")
        if "transporter" in payload:
            payload["transporter"] = str(int(transporters))
        elif "transporters" in payload:
            payload["transporters"] = str(int(transporters))

    form_id = str(form.get("id") or "")
    is_barbarian = "barbarianVillage" in payload or payload.get("function") == "attackBarbarianVillage"
    template_view = (
        "plunder"
        if form_id == "plunderForm" or "plunder" in str(payload.get("function") or "").lower() or is_barbarian
        else "deployment"
    )
    if template_view == "deployment" and "deploymentType" not in payload:
        payload["deploymentType"] = (
            "fleet" if payload.get("function") == "deployFleet" else "army"
        )

    params: Dict[str, str] = {
        "templateView": template_view,
        "actionRequest": "REQUESTID",
        "ajax": "1",
    }
    if is_barbarian and payload.get("islandId"):
        params["backgroundView"] = "island"
        params["currentIslandId"] = str(payload["islandId"])
    else:
        params["backgroundView"] = "city"
        cur_id = origin_city_id or (
            client.selectedDropDownCity.id if client.selectedDropDownCity is not None else None
        )
        if cur_id:
            params["currentCityId"] = str(cur_id)

    if origin_city_id is not None:
        await _select_city_id(client, origin_city_id, action_name=action_name)

    return await client.post_action(
        payloadPost=payload,
        params=params,
        metadata={"ambrosia_cost": 0},
        action_name=action_name,
    )


class TransportView:
    """View representing the transport mission configuration screen."""

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

    def __init__(
        self,
        viewData: str,
        client: Optional["Client"] = None,
        originCityId: Optional[int] = None,
    ) -> None:
        """Parse ``transportConfig`` values from the transport view HTML or AJAX JSON."""
        self._client = client
        self._origin_city_id = originCityId
        html = _extract_view_html(viewData)
        config_block = extract_js_object(html, "transportConfig")
        if config_block is None:
            if "journeyDuration" not in html:
                raise ValueError("Could not find transportConfig in transport view")
            config_block = html

        self.journeyDuration = parse_int(_extract_js_number(config_block, "journeyDuration")) or 0
        self.transporterSpeed = parse_int(_extract_js_number(config_block, "transporterSpeed")) or 0
        self.baseJourneyTime = parse_int(_extract_js_number(config_block, "fleetJourneyTime")) or 0
        self.distance = parse_float(_extract_js_number(config_block, "distance")) or 0.0
        self.loadingSpeed = parse_float(_extract_js_number(config_block, "loadingSpeed")) or 0.0
        self.poseidonBonus = parse_float(_extract_js_number(config_block, "poseidonEffect")) or 0.0
        self.governmentBonus = parse_float(_extract_js_number(config_block, "governmentBonus")) or 0.0
        self.marineChartArchiveBonus = (
            parse_float(_extract_js_number(config_block, "marineChartArchiveBonus")) or 0.0
        )
        self.worldBonus = parse_float(_extract_js_number(config_block, "worldBonus")) or 0.0
        self.tritonInjectorLevel = (
            parse_float(_extract_js_number(config_block, "tritonInjectorLevel")) or 0.0
        )
        self.minimumJourneyTime = (
            parse_int(_extract_js_number(config_block, "minimumJourneyDuration")) or 0
        )
        self.needsLoading = (parse_int(_extract_js_number(config_block, "needsLoading")) or 0) == 1
        queue_ts = parse_int(_extract_js_number(config_block, "queueTime"))
        self.queueTime = datetime.fromtimestamp(queue_ts) if queue_ts and queue_ts > 0 else None
        self._transport_view_view_data = viewData

    def getJourneyDuration(self) -> int:
        """Return the base journey duration in seconds."""
        return self.journeyDuration

    async def send(
        self,
        resources: Optional[Union[Resources, Sequence[Resource], Dict[str, int]]] = None,
        *,
        wood: int = 0,
        wine: int = 0,
        marble: int = 0,
        crystal: int = 0,
        sulphur: int = 0,
        transporters: Optional[int] = None,
        freighters: int = 0,
        client: Optional["Client"] = None,
    ) -> AjaxResponse:
        """Dispatch the configured resource transport using merchant ships and/or freighters."""
        active_client = client or self._client
        if active_client is None:
            raise ValueError("TransportView is not bound to an active Client")

        html = _extract_view_html(self._transport_view_view_data)
        form = make_soup(html).select_one("#transportForm")
        if form is None:
            raise ValueError("Could not find #transportForm in transport view")

        payload = _collect_form_inputs(form)
        cargo = _normalize_resource_amounts(
            resources,
            wood=wood,
            wine=wine,
            marble=marble,
            crystal=crystal,
            sulphur=sulphur,
        )
        payload.update({k: str(v) for k, v in cargo.items()})

        if freighters < 0 or (transporters is not None and transporters < 0):
            raise ValueError("Ship counts cannot be negative")

        total_cargo = sum(cargo.values())
        if freighters == 0 and transporters is None:
            transporters = max(1, math.ceil(total_cargo / 500))

        # Always keep Ambrosia-chartered mercenary transporters disabled.
        payload["premiumTransporter"] = "0"
        payload["transportDisplayPrice"] = "0"
        payload["usedFreightersShips"] = str(int(freighters))
        payload["transporters"] = str(int(transporters or 0))

        cur_id = self._origin_city_id or (
            active_client.selectedDropDownCity.id
            if active_client.selectedDropDownCity is not None
            else None
        )
        if self._origin_city_id is not None:
            await _select_city_id(
                active_client,
                self._origin_city_id,
                action_name="TransportView.send",
            )
        params: Dict[str, str] = {
            "backgroundView": "city",
            "templateView": "transport",
            "currentTab": "tabSendTransporter",
            "actionRequest": "REQUESTID",
            "ajax": "1",
        }
        if cur_id:
            params["currentCityId"] = str(cur_id)

        return await active_client.post_action(
            payloadPost=payload,
            params=params,
            metadata={"ambrosia_cost": 0},
            action_name="TransportView.send",
        )


class SendUnitsView:
    """View representing a military or fleet mission deployment screen."""

    availableUnits: List[Unit]

    def __init__(
        self,
        viewData: str,
        client: Optional["Client"] = None,
        originCityId: Optional[int] = None,
    ) -> None:
        """Parse available units from ``units = JSON.parse(...)`` in the mission view."""
        self._client = client
        self._origin_city_id = originCityId
        html = _extract_view_html(viewData)
        available_units_data = extract_js_json_parse(html, "units")
        self.availableUnits = []
        if isinstance(available_units_data, dict):
            for unit_id, unit_info in available_units_data.items():
                parsed_id = parse_int(unit_id)
                unit_template = Units.getUnitById(parsed_id) if parsed_id is not None else None
                amount = parse_int(unit_info.get("amount")) if isinstance(unit_info, dict) else None
                if unit_template is not None and amount is not None:
                    self.availableUnits.append(unit_template(amount))
        self._send_units_view_data = viewData

    async def send(
        self,
        units: Union[
            Sequence[Unit],
            Dict[Union[int, str, Unit], int],
            Sequence[Tuple[Union[int, str, Unit], int]],
        ],
        *,
        transporters: Optional[int] = None,
        client: Optional["Client"] = None,
    ) -> AjaxResponse:
        """Dispatch the selected army units or warships for this mission."""
        active_client = client or self._client
        if active_client is None:
            raise ValueError("SendUnitsView is not bound to an active Client")
        html = _extract_view_html(self._send_units_view_data)
        return await _submit_unit_mission_form(
            active_client,
            html,
            units,
            transporters=transporters,
            available_units=self.availableUnits,
            origin_city_id=self._origin_city_id,
            action_name="SendUnitsView.send",
        )


def _parse_countdown_entry(
    entry: Any,
) -> Tuple[Optional[datetime], Optional[int], Optional[int]]:
    """Extract ``(end_datetime, end_ts, remaining_seconds)`` from an AJAX countdown entry."""
    if not isinstance(entry, dict):
        return None, None, None
    countdown = entry.get("countdown") if isinstance(entry.get("countdown"), dict) else entry
    if not isinstance(countdown, dict):
        return None, None, None

    end_ts = parse_int(countdown.get("enddate"))
    cur_ts = parse_int(countdown.get("currentdate"))
    end_dt = datetime.fromtimestamp(end_ts) if end_ts and end_ts > 0 else None
    remaining: Optional[int] = None
    if end_ts is not None and end_ts > 0 and cur_ts is not None:
        remaining = max(0, end_ts - cur_ts)
    return end_dt, (end_ts if end_ts and end_ts > 0 else None), remaining


def _td_visible(
    resp: AjaxResponse,
    container: Tag,
    selector_key: str,
    css_selector: str,
    default: bool = False,
) -> bool:
    """Return whether a row sub-element is visible after applying ``template_data`` styles."""
    entry = resp.template_data.get(selector_key)
    if isinstance(entry, dict):
        style = entry.get("style")
        if isinstance(style, dict) and "display" in style:
            return str(style["display"]).strip().lower() != "none"

    el = container.select_one(css_selector)
    if el is None:
        return default
    raw_style = str(el.get("style") or "")
    match = re.search(r"display\s*:\s*([^;]+)", raw_style, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower() != "none"
    return default


def _parse_pure_int(text: str) -> Optional[int]:
    """Parse an integer only when ``text`` represents a formatted number rather than a duration."""
    stripped = text.strip()
    if not stripped or not re.fullmatch(r"[+-]?[\d.,\s]+", stripped):
        return None
    return parse_int(stripped)


def _extract_first_int(text: Optional[str]) -> Optional[int]:
    """Extract the first formatted integer from mixed UI text such as ``'Day 1'``."""
    if not text:
        return None
    match = re.search(r"\d[\d.,]*", text)
    return parse_int(match.group(0)) if match else None


class DailyTaskEntry:
    """Represents a single row in the Daily Tasks list (IDs rotate daily)."""

    id: int
    name: str
    difficulty: Optional[str]
    currentAmount: Optional[int]
    targetAmount: Optional[int]
    progressText: Optional[str]
    progressMode: str
    resourceTitle: Optional[str]
    favor: int
    isCompleted: bool
    isCollected: bool
    canCollect: bool
    canSpeedup: bool
    speedupAmbrosiaCost: Optional[int]
    collectHref: Optional[str]
    speedupHref: Optional[str]

    def __init__(
        self,
        *,
        taskId: int,
        name: str,
        difficulty: Optional[str],
        currentAmount: Optional[int],
        targetAmount: Optional[int],
        progressText: Optional[str],
        progressMode: str,
        resourceTitle: Optional[str],
        favor: int,
        isCompleted: bool,
        isCollected: bool,
        canCollect: bool,
        canSpeedup: bool,
        speedupAmbrosiaCost: Optional[int],
        collectHref: Optional[str],
        speedupHref: Optional[str],
    ) -> None:
        self.id = taskId
        self.name = name
        self.difficulty = difficulty
        self.currentAmount = currentAmount
        self.targetAmount = targetAmount
        self.progressText = progressText
        self.progressMode = progressMode
        self.resourceTitle = resourceTitle
        self.favor = favor
        self.isCompleted = isCompleted
        self.isCollected = isCollected
        self.canCollect = canCollect
        self.canSpeedup = canSpeedup
        self.speedupAmbrosiaCost = speedupAmbrosiaCost
        self.collectHref = collectHref
        self.speedupHref = speedupHref


class DailyTaskRewardEntry:
    """Represents a single redeemable reward on the Daily Tasks Rewards tab."""

    id: int
    name: str
    description: str
    amount: Optional[int]
    favorCost: int
    canRedeem: bool
    applicableToCity: bool
    disabledReason: Optional[str]
    redeemHref: Optional[str]
    iconClass: Optional[str]

    def __init__(
        self,
        *,
        rewardId: int,
        name: str,
        description: str,
        amount: Optional[int],
        favorCost: int,
        canRedeem: bool,
        applicableToCity: bool,
        disabledReason: Optional[str],
        redeemHref: Optional[str],
        iconClass: Optional[str],
    ) -> None:
        self.id = rewardId
        self.name = name
        self.description = description
        self.amount = amount
        self.favorCost = favorCost
        self.canRedeem = canRedeem
        self.applicableToCity = applicableToCity
        self.disabledReason = disabledReason
        self.redeemHref = redeemHref
        self.iconClass = iconClass


class DailyTasksView:
    """View model for the city Daily Tasks popup and its Rewards tab."""

    # Note: Daily tasks rotate every 24 hours, so task IDs and task definitions
    # are not statically enumerable; rows must always be parsed dynamically.

    city: Optional[City]
    favor: int
    favorLimit: int
    tasksDone: int
    tasksCount: int
    tasksSolvedHeader: str
    countdownEnd: Optional[datetime]
    countdownTimestamp: Optional[int]
    remainingSeconds: Optional[int]
    hasRefreshProgress: bool
    refreshProgressHref: Optional[str]
    tasks: List[DailyTaskEntry]
    rewards: List[DailyTaskRewardEntry]

    def __init__(
        self,
        viewData: Union[str, AjaxResponse],
        rewardsViewData: Optional[Union[str, AjaxResponse]] = None,
        city: Optional[City] = None,
    ) -> None:
        """Parse Daily Tasks (and optional Rewards tab) from HTML or AJAX payloads."""
        self.city = city
        self.favor = 0
        self.favorLimit = 0
        self.tasksDone = 0
        self.tasksCount = 0
        self.tasksSolvedHeader = ""
        self.countdownEnd = None
        self.countdownTimestamp = None
        self.remainingSeconds = None
        self.hasRefreshProgress = False
        self.refreshProgressHref = None
        self.tasks = []
        self.rewards = []
        self._daily_tasks_response: Optional[AjaxResponse] = None
        self._daily_tasks_rewards_response: Optional[AjaxResponse] = None

        resp, soup = parse_view_payload(viewData)
        if resp.view_name == "dailyTasksRewards" or (
            isinstance(resp.template_data.get("currentRewards"), dict)
            and not soup.select("tr[id^='task_row_']")
        ):
            self._parse_rewards_tab(resp, soup)
        else:
            self._parse_tasks_tab(resp, soup)

        if rewardsViewData is not None:
            r_resp, r_soup = parse_view_payload(rewardsViewData)
            self._parse_rewards_tab(r_resp, r_soup)

    def _parse_tasks_tab(self, resp: AjaxResponse, soup: BeautifulSoup) -> None:
        """Populate task rows, favor balance, and reset countdown from the Tasks tab."""
        self._daily_tasks_response = resp
        favor_el = soup.select_one("#currentFavor")
        parsed_favor = tmpl_int(resp, "currentFavor")
        if parsed_favor is None and favor_el is not None:
            parsed_favor = parse_int(favor_el.get_text(" ", strip=True))
        self.favor = parsed_favor or 0

        parsed_limit = tmpl_int(resp, "favorLimit")
        if parsed_limit is None and favor_el is not None and favor_el.get("data-limit"):
            parsed_limit = parse_int(str(favor_el["data-limit"]))
        self.favorLimit = parsed_limit or 0

        end_dt, end_ts, rem_secs = _parse_countdown_entry(
            resp.template_data.get("dailyTasksCountdown")
        )
        self.countdownEnd = end_dt
        self.countdownTimestamp = end_ts
        self.remainingSeconds = rem_secs

        solved_el = soup.select_one("#tasksSolvedHeader")
        self.tasksSolvedHeader = tmpl_text(resp, "tasksSolvedHeader") or (
            solved_el.get_text(" ", strip=True) if solved_el else ""
        )

        refresh_btn = soup.select_one("a[href*='UpdatePassiveTasksProgress']")
        self.hasRefreshProgress = refresh_btn is not None
        self.refreshProgressHref = (
            str(refresh_btn["href"]) if refresh_btn and refresh_btn.get("href") else None
        )

        # Dynamically iterate rows because rotating daily tasks introduce varying task IDs.
        current_difficulty: Optional[str] = None
        for tr in soup.select("table.table01 tr"):
            header_td = tr.select_one("td.sectionHeader")
            if header_td is not None:
                text = " ".join(
                    str(s).strip()
                    for s in header_td.find_all(string=True, recursive=False)
                    if str(s).strip()
                )
                current_difficulty = text or None
                continue

            raw_id = str(tr.get("id") or "")
            if not raw_id.startswith("task_row_"):
                continue
            task_id = parse_int(raw_id[len("task_row_") :])
            if task_id is None:
                continue

            row_td = resp.template_data.get(f"task_row_{task_id}")
            if isinstance(row_td, dict) and "class" in row_td:
                row_classes = str(row_td.get("class") or "").split()
            else:
                row_classes = list(tr.get("class") or [])

            name_el = tr.select_one("td.taskName")
            name = tmpl_text(resp, f"task_row_{task_id} .taskName") or (
                name_el.get_text(" ", strip=True) if name_el else ""
            )

            ach_visible = _td_visible(
                resp, tr, f"task_row_{task_id} .achievementCheck", "img.achievementCheck"
            )
            can_collect = _td_visible(
                resp, tr, f"task_row_{task_id} .favorWithButton", "td.favorWithButton"
            )
            is_collected = "textLineThrough" in row_classes and not can_collect

            if _td_visible(resp, tr, f"task_row_{task_id} .progress.watch", "td.progress.watch"):
                progress_mode = "watch"
            elif _td_visible(
                resp, tr, f"task_row_{task_id} .progress.noDetails", "td.progress.noDetails"
            ):
                progress_mode = "noDetails"
            else:
                progress_mode = "details"

            amt_el = tr.select_one(f"#task_amount_{task_id}")
            amt_text = tmpl_text(resp, f"task_amount_{task_id}") or (
                amt_el.get_text(" ", strip=True) if amt_el else ""
            )
            current_amount = _parse_pure_int(amt_text)

            details_tds = tr.select("td.progress.details")
            target_amount = (
                _parse_pure_int(details_tds[2].get_text(" ", strip=True))
                if len(details_tds) >= 3
                else None
            )

            progress_text: Optional[str] = None
            if progress_mode == "watch":
                watch_td = tr.select_one("td.progress.watch")
                progress_text = (
                    (watch_td.get_text(" ", strip=True) if watch_td else "") or amt_text or None
                )
            elif current_amount is not None and target_amount is not None:
                progress_text = f"{current_amount} / {target_amount}"
            elif amt_text:
                progress_text = amt_text

            icon_scope = (
                tr.select("td.progress.watch img")
                if progress_mode == "watch"
                else tr.select("td.progress.details img")
            )
            resource_title = next(
                (
                    str(img.get("title") or img.get("alt"))
                    for img in icon_scope
                    if img.get("title") or img.get("alt")
                ),
                None,
            )

            collect_btn = tr.select_one("a.collectDailyFavor")
            collect_href = (
                str(collect_btn["href"]) if collect_btn and collect_btn.get("href") else None
            )
            favor = (
                parse_int(str(collect_btn["data-task-favor"]))
                if collect_btn and collect_btn.get("data-task-favor")
                else None
            )
            if favor is None:
                favor_wo = tr.select_one("td.favorWithoutButton")
                favor = parse_int(favor_wo.get_text(" ", strip=True)) if favor_wo else None

            speedup_btn = tr.select_one("a.buildingSpeedupButton")
            speedup_href = (
                str(speedup_btn["href"]) if speedup_btn and speedup_btn.get("href") else None
            )
            raw_price = (
                parse_int(str(speedup_btn["data-price"]))
                if speedup_btn and speedup_btn.get("data-price")
                else None
            )
            speedup_cost = raw_price if raw_price is not None and raw_price >= 0 else None
            can_speedup = (
                _td_visible(
                    resp,
                    tr,
                    f"task_row_{task_id} .buildingSpeedupButton",
                    "a.buildingSpeedupButton",
                )
                and speedup_cost is not None
            )

            is_completed = (
                is_collected
                or ach_visible
                or can_collect
                or (
                    current_amount is not None
                    and target_amount is not None
                    and target_amount > 0
                    and current_amount >= target_amount
                )
            )

            self.tasks.append(
                DailyTaskEntry(
                    taskId=task_id,
                    name=name,
                    difficulty=current_difficulty,
                    currentAmount=current_amount,
                    targetAmount=target_amount,
                    progressText=progress_text,
                    progressMode=progress_mode,
                    resourceTitle=resource_title,
                    favor=favor or 0,
                    isCompleted=is_completed,
                    isCollected=is_collected,
                    canCollect=can_collect,
                    canSpeedup=can_speedup,
                    speedupAmbrosiaCost=speedup_cost,
                    collectHref=collect_href,
                    speedupHref=speedup_href,
                )
            )

        done_td = tmpl_int(resp, "tasksDone")
        count_td = tmpl_int(resp, "tasksCount")
        self.tasksDone = (
            done_td if done_td is not None else sum(1 for t in self.tasks if t.isCompleted)
        )
        self.tasksCount = count_td if count_td is not None else len(self.tasks)

    def _parse_rewards_tab(self, resp: AjaxResponse, soup: BeautifulSoup) -> None:
        """Populate redeemable favor rewards from the Daily Tasks Rewards tab."""
        self._daily_tasks_rewards_response = resp
        favour_td = tmpl_int(resp, "currentFavour")
        if favour_td is not None and self.favor == 0:
            self.favor = favour_td
        if self.countdownEnd is None:
            end_dt, end_ts, rem_secs = _parse_countdown_entry(
                resp.template_data.get("dailyTasksCountdown")
            )
            self.countdownEnd = end_dt
            self.countdownTimestamp = end_ts
            self.remainingSeconds = rem_secs

        current_rewards = resp.template_data.get("currentRewards")
        if not isinstance(current_rewards, dict):
            current_rewards = {}

        seen_ids = set()
        for btn in soup.select("a[id^='rewardButton'], a[href*='ChangeFavorIntoReward']"):
            btn_id = str(btn.get("id") or "")
            href = str(btn.get("href") or "") or None
            reward_id: Optional[int] = None
            if btn_id.startswith("rewardButton"):
                reward_id = parse_int(btn_id[len("rewardButton") :])
            if reward_id is None and href:
                reward_id = parse_int(parse_query_str(href, "rewardId"))
            if reward_id is None or reward_id in seen_ids:
                continue
            seen_ids.add(reward_id)

            meta = current_rewards.get(str(reward_id))
            if not isinstance(meta, dict):
                meta = {}

            tr = btn.find_parent("tr")
            tds = tr.find_all("td") if tr is not None else []
            description = (
                tds[1].get_text(" ", strip=True)
                if len(tds) >= 2
                else str(meta.get("name") or "")
            )
            name = str(meta.get("name") or description)
            amount = parse_int(meta.get("rewardAmount"))
            favor_cost = parse_int(meta.get("favour"))
            if favor_cost is None and len(tds) >= 3:
                favor_cost = parse_int(tds[2].get_text(" ", strip=True))

            btn_td = resp.template_data.get(f"rewardButton{reward_id}")
            if isinstance(btn_td, dict) and "class" in btn_td:
                btn_classes = str(btn_td.get("class") or "").split()
            else:
                btn_classes = list(btn.get("class") or [])
            can_redeem = "button_disabled" not in btn_classes

            tip_td = resp.template_data.get(f"rewardButtonTooltip{reward_id}")
            disabled_reason: Optional[str] = None
            if (
                isinstance(tip_td, dict)
                and tip_td.get("class") != "invisible"
                and tip_td.get("text")
            ):
                disabled_reason = make_soup(str(tip_td["text"])).get_text(" ", strip=True) or None

            applicable = (
                bool(meta["3"])
                if "3" in meta
                else ("no effect" not in (disabled_reason or "").lower())
            )
            icon_class = str(meta.get("class")) if meta.get("class") else None

            self.rewards.append(
                DailyTaskRewardEntry(
                    rewardId=reward_id,
                    name=name,
                    description=description,
                    amount=amount,
                    favorCost=favor_cost or 0,
                    canRedeem=can_redeem,
                    applicableToCity=applicable,
                    disabledReason=disabled_reason,
                    redeemHref=href,
                    iconClass=icon_class,
                )
            )

        self._rewards_parsed_from_dom = True

    async def loadRewards(self) -> List[DailyTaskRewardEntry]:
        """Fetch and populate the Rewards tab if bound to an active city (read-only)."""
        if self.city is None:
            raise ValueError("DailyTasksView is not bound to a City")
        resp = await self.city._fetch_city_view(
            "dailyTasksRewards",
            activeTab="tab_dailyTasksRewards",
        )
        self.rewards = []
        self._parse_rewards_tab(resp, make_soup(resp.view_html or ""))
        return self.rewards

    @property
    def collectableTasks(self) -> List[DailyTaskEntry]:
        """Return tasks whose favor reward is ready to be collected."""
        return [task for task in self.tasks if task.canCollect]

    @property
    def incompleteTasks(self) -> List[DailyTaskEntry]:
        """Return tasks not yet completed today."""
        return [task for task in self.tasks if not task.isCompleted]

    @property
    def redeemableRewards(self) -> List[DailyTaskRewardEntry]:
        """Return rewards currently redeemable with available favor."""
        return [reward for reward in self.rewards if reward.canRedeem]

    def getTask(self, taskId: int) -> Optional[DailyTaskEntry]:
        """Return the task entry matching ``taskId``, or ``None`` if absent."""
        return next((task for task in self.tasks if task.id == taskId), None)

    def getReward(self, rewardId: int) -> Optional[DailyTaskRewardEntry]:
        """Return the reward entry matching ``rewardId``, or ``None`` if absent."""
        return next((reward for reward in self.rewards if reward.id == rewardId), None)

    async def refreshProgress(self) -> "DailyTasksView":
        """Trigger server-side refresh of passive daily task progress and reload tasks."""
        if self.city is None or self.city.client is None:
            raise ValueError("DailyTasksView is not bound to a City with an active Client")
        params: Dict[str, str] = {"action": "UpdatePassiveTasksProgress"}
        if self.refreshProgressHref:
            params.update(parse_query_params(self.refreshProgressHref))
        params.setdefault("backgroundView", "city")
        params.setdefault("currentCityId", str(self.city.id))
        params.setdefault("templateView", "dailyTasks")
        params.setdefault("actionRequest", "REQUESTID")
        resp = await self.city.client.post_action(
            params=params,
            metadata={"ambrosia_cost": 0},
            action_name="DailyTasksView.refreshProgress",
        )
        if not (resp.view_html and "task_row_" in resp.view_html):
            resp = await self.city._fetch_city_view("dailyTasks")
        self.tasks = []
        self._parse_tasks_tab(resp, make_soup(resp.view_html or ""))
        return self

    async def collectTaskFavor(self, taskId: int) -> AjaxResponse:
        """Collect the favor reward for a completed daily task."""
        if self.city is None or self.city.client is None:
            raise ValueError("DailyTasksView is not bound to a City with an active Client")
        task = self.getTask(taskId)
        if task is None:
            raise ValueError(f"Daily task {taskId} was not found.")
        if task.isCollected:
            raise ValueError(f"Daily task {taskId} ({task.name}) was already collected.")
        if not task.canCollect:
            raise ValueError(
                f"Daily task {taskId} ({task.name}) cannot be collected yet ({task.progressText})."
            )

        query = parse_query_params(
            task.collectHref or f"?action=CollectDailyTasksFavor&taskId={taskId}"
        )
        params: Dict[str, str] = {
            **query,
            "backgroundView": "city",
            "currentCityId": str(self.city.id),
            "templateView": "dailyTasks",
            "actionRequest": "REQUESTID",
            "ajax": "1",
        }
        resp = await self.city.client.post_action(
            params=params,
            metadata={"cityId": self.city.id, "taskId": taskId, "ambrosia_cost": 0},
            action_name=f"DailyTasksView.collectTaskFavor({taskId})",
        )
        if resp.view_html and "task_row_" in resp.view_html:
            self.tasks = []
            self._parse_tasks_tab(resp, make_soup(resp.view_html))
        else:
            refreshed = await self.city._fetch_city_view("dailyTasks")
            self.tasks = []
            self._parse_tasks_tab(refreshed, make_soup(refreshed.view_html or ""))
        return resp

    async def speedupTask(self, taskId: int) -> AjaxResponse:
        """Complete a daily task immediately by spending Ambrosia."""
        ...

    async def redeemReward(self, rewardId: int) -> AjaxResponse:
        """Exchange favor for a daily tasks reward item or resource pack."""
        if not self.rewards:
            await self.loadRewards()

        reward = self.getReward(rewardId)
        if reward is None:
            raise ValueError(f"Daily task reward {rewardId} was not found.")
        if not reward.canRedeem:
            raise ValueError(
                f"Daily task reward {rewardId} ({reward.name}) cannot be redeemed: "
                f"{reward.disabledReason or 'unavailable'}."
            )

        query = parse_query_params(
            reward.redeemHref or f"?action=ChangeFavorIntoReward&rewardId={rewardId}"
        )
        payload: Dict[str, str] = {
            **query,
            "backgroundView": "city",
            "currentCityId": str(self.city.id),
            "templateView": "dailyTasksRewards",
            "actionRequest": "REQUESTID",
            "ajax": "1",
        }
        resp = await self.city.client.post_action(
            payloadPost=payload,
            metadata={
                "cityId": self.city.id,
                "rewardId": rewardId,
                "favorCost": reward.favorCost,
            },
            action_name=f"DailyTasksView.redeemReward({rewardId})",
        )
        await self.loadRewards()
        if self._daily_tasks_rewards_response is not None:
            updated_favor = tmpl_int(self._daily_tasks_rewards_response, "currentFavour")
            if updated_favor is not None:
                self.favor = updated_favor
        return resp


class CinemaRewardEntry:
    """Represents a single video bonus option inside the Cinetheatre."""

    key: str
    bonusId: Optional[int]
    title: str
    subtitle: str
    bonusText: str
    available: bool
    nextAvailable: Optional[datetime]
    nextAvailableTimestamp: Optional[int]
    remainingSeconds: int
    remainingText: Optional[str]
    countdownId: Optional[str]
    formId: Optional[str]
    submitId: Optional[str]

    def __init__(
        self,
        *,
        key: str,
        bonusId: Optional[int],
        title: str,
        subtitle: str,
        bonusText: str,
        available: bool,
        nextAvailable: Optional[datetime],
        nextAvailableTimestamp: Optional[int],
        remainingSeconds: int,
        remainingText: Optional[str],
        countdownId: Optional[str],
        formId: Optional[str],
        submitId: Optional[str],
    ) -> None:
        self.key = key
        self.bonusId = bonusId
        self.title = title
        self.subtitle = subtitle
        self.bonusText = bonusText
        self.available = available
        self.nextAvailable = nextAvailable
        self.nextAvailableTimestamp = nextAvailableTimestamp
        self.remainingSeconds = remainingSeconds
        self.remainingText = remainingText
        self.countdownId = countdownId
        self.formId = formId
        self.submitId = submitId


class CinemaView:
    """View model for the city Cinetheatre video bonus screen."""

    city: Optional[City]
    videoId: Optional[int]
    uid: Optional[str]
    highlight: bool
    gameUrl: Optional[str]
    culturalVideoFavor: int
    videos: List[Dict[str, Any]]
    rewards: List[CinemaRewardEntry]

    def __init__(
        self,
        viewData: Union[str, AjaxResponse],
        city: Optional[City] = None,
    ) -> None:
        """Parse Cinetheatre rewards, exact cooldown timestamps, and video metadata."""
        self.city = city
        resp, soup = parse_view_payload(viewData)
        td = resp.template_data

        self.videoId = parse_int(td.get("videoID"))
        self.uid = None
        self.videos = []
        load_js = td.get("load_js")
        if isinstance(load_js, dict) and load_js.get("params"):
            raw_params = load_js.get("params")
            try:
                params_obj = (
                    json.loads(raw_params) if isinstance(raw_params, str) else raw_params
                )
            except (TypeError, json.JSONDecodeError):
                params_obj = None
            if isinstance(params_obj, dict):
                self.uid = str(params_obj["uid"]) if params_obj.get("uid") else None
                if self.videoId is None:
                    self.videoId = parse_int(params_obj.get("videoID"))
                if isinstance(params_obj.get("videos"), list):
                    self.videos = [
                        v for v in params_obj["videos"] if isinstance(v, dict)
                    ]

        self.highlight = bool(td.get("highlight", False))
        raw_game_url = td.get("gameURL")
        self.gameUrl = str(raw_game_url) if raw_game_url else None
        self.culturalVideoFavor = parse_int(td.get("cinema .culturalVideoFavor")) or 0

        self.rewards = []
        rewards_data = td.get("rewards")
        if isinstance(rewards_data, list):
            for entry in rewards_data:
                if not isinstance(entry, dict):
                    continue
                countdown_id = (
                    str(entry["countdownId"]) if entry.get("countdownId") else None
                )
                end_dt, end_ts, rem_secs = (
                    _parse_countdown_entry(td.get(countdown_id))
                    if countdown_id
                    else (None, None, None)
                )
                if end_ts is None:
                    raw_next = parse_int(entry.get("nextAvailable"))
                    if raw_next and raw_next > 0:
                        end_ts = raw_next
                        end_dt = datetime.fromtimestamp(raw_next)

                rem_el = soup.find(id=countdown_id) if countdown_id else None
                rem_text = rem_el.get_text(" ", strip=True) if rem_el else None
                available = bool(entry.get("available", False))
                if rem_secs is None:
                    rem_secs = 0 if available else (parse_duration_seconds(rem_text) or 0)

                subtitle = (
                    make_soup(str(entry["subtitleHtml"])).get_text(" ", strip=True)
                    if entry.get("subtitleHtml")
                    else ""
                )
                bonus_text = (
                    make_soup(str(entry["bonusText"])).get_text(" ", strip=True)
                    if entry.get("bonusText")
                    else ""
                )

                self.rewards.append(
                    CinemaRewardEntry(
                        key=str(entry.get("key") or ""),
                        bonusId=parse_int(entry.get("bonusId")),
                        title=str(entry.get("title") or ""),
                        subtitle=subtitle,
                        bonusText=bonus_text,
                        available=available,
                        nextAvailable=end_dt,
                        nextAvailableTimestamp=end_ts,
                        remainingSeconds=rem_secs,
                        remainingText=rem_text,
                        countdownId=countdown_id,
                        formId=str(entry["formId"]) if entry.get("formId") else None,
                        submitId=str(entry["submitId"]) if entry.get("submitId") else None,
                    )
                )

        self._cinema_response = resp

    @property
    def availableRewards(self) -> List[CinemaRewardEntry]:
        """Return the Cinetheatre rewards currently available to watch."""
        return [reward for reward in self.rewards if reward.available]

    def getReward(self, keyOrBonusId: Union[str, int]) -> Optional[CinemaRewardEntry]:
        """Look up a reward entry by string key (e.g. ``'favour'``) or ``bonusId``."""
        if isinstance(keyOrBonusId, int):
            return next((r for r in self.rewards if r.bonusId == keyOrBonusId), None)
        return next((r for r in self.rewards if r.key == keyOrBonusId), None)

    async def requestBonus(
        self,
        bonusId: int,
        videoId: Optional[int] = None,
    ) -> AjaxResponse:
        """Request to start watching a Cinetheatre ad reward video."""
        ...

    async def watchVideo(
        self,
        bonusId: int,
        videoId: Optional[int] = None,
    ) -> AjaxResponse:
        """Complete watching the Cinetheatre video and claim its bonus."""
        ...


class AmbrosiaFountainDay:
    """Single day entry in the Divine Ambrosia Fountain daily reward track."""

    day: int
    ambrosiaAmount: int
    isCurrent: bool
    isCollected: bool

    def __init__(
        self,
        *,
        day: int,
        ambrosiaAmount: int,
        isCurrent: bool = False,
        isCollected: bool = False,
    ) -> None:
        self.day = day
        self.ambrosiaAmount = ambrosiaAmount
        self.isCurrent = isCurrent
        self.isCollected = isCollected


class AmbrosiaFountainView:
    """View model for the capital's Divine Ambrosia Fountain popup."""

    city: Optional[City]
    isActive: bool
    canCollect: bool
    canActivate: bool
    canExtend: bool
    missingAmbrosia: Optional[int]
    buyHref: Optional[str]
    extendHref: Optional[str]
    nextCollectionEnd: Optional[datetime]
    nextCollectionTimestamp: Optional[int]
    nextCollectionRemainingSeconds: Optional[int]
    expirationEnd: Optional[datetime]
    expirationTimestamp: Optional[int]
    expirationRemainingSeconds: Optional[int]
    days: List[AmbrosiaFountainDay]

    def __init__(
        self,
        viewData: Union[str, AjaxResponse],
        city: Optional[City] = None,
    ) -> None:
        """Parse Divine Ambrosia Fountain state, countdowns, and daily reward schedule."""
        self.city = city
        resp, soup = parse_view_payload(viewData)
        td = resp.template_data

        fountain_img = soup.select_one("div.fountainImg")
        img_classes = list(fountain_img.get("class") or []) if fountain_img else []

        next_dt, next_ts, next_secs = _parse_countdown_entry(
            td.get("fountainNextCollection")
        )
        exp_dt, exp_ts, exp_secs = _parse_countdown_entry(td.get("fountainEndCountdown"))
        self.nextCollectionEnd = next_dt
        self.nextCollectionTimestamp = next_ts
        self.nextCollectionRemainingSeconds = next_secs
        self.expirationEnd = exp_dt
        self.expirationTimestamp = exp_ts
        self.expirationRemainingSeconds = exp_secs

        self.isActive = (
            ("buy" not in img_classes) if fountain_img else (exp_dt is not None)
        )
        if exp_dt is not None:
            self.isActive = True

        collect_btn = soup.select_one("#fountainCollectButton")
        collect_td = td.get("fountainCollectButton")
        collect_td_classes = (
            str(collect_td.get("class") or "").split()
            if isinstance(collect_td, dict)
            else []
        )
        collect_classes = (
            set(collect_btn.get("class") or []) | set(collect_td_classes)
            if collect_btn is not None
            else set()
        )
        self.canCollect = collect_btn is not None and "button_disabled" not in collect_classes

        buy_text_el = soup.select_one("#js_buyAmbrosiaText")
        self.missingAmbrosia = (
            _extract_first_int(buy_text_el.get_text(" ", strip=True))
            if buy_text_el is not None
            else None
        )

        buy_link = soup.select_one(
            "a[href*='AmbrosiaFountainActions'][href*='function=buy'], a[onclick*='abortBuy']"
        )
        extend_link = soup.select_one(
            "a[href*='AmbrosiaFountainActions'][href*='function=extend'], a[onclick*='abortExtend']"
        )
        self.canActivate = buy_link is not None
        self.canExtend = extend_link is not None
        self.buyHref = (
            str(buy_link["href"])
            if buy_link and buy_link.get("href")
            else ("?action=AmbrosiaFountainActions&function=buy" if self.canActivate else None)
        )
        self.extendHref = (
            str(extend_link["href"])
            if extend_link and extend_link.get("href")
            else ("?action=AmbrosiaFountainActions&function=extend" if self.canExtend else None)
        )

        self.days = []
        for idx, box in enumerate(soup.select("table.fountainTable div.highlightbox"), start=1):
            inner_divs = box.find_all("div", recursive=False)
            day_num = (
                _extract_first_int(inner_divs[0].get_text(" ", strip=True))
                if inner_divs
                else idx
            )
            amt = (
                _extract_first_int(inner_divs[1].get_text(" ", strip=True))
                if len(inner_divs) >= 2
                else 0
            )
            box_classes = set(box.get("class") or [])
            td_parent = box.find_parent("td")
            parent_classes = set(td_parent.get("class") or []) if td_parent else set()
            all_classes = box_classes | parent_classes
            self.days.append(
                AmbrosiaFountainDay(
                    day=day_num if day_num is not None else idx,
                    ambrosiaAmount=amt or 0,
                    isCurrent=bool(all_classes & {"active", "current", "fountain_active"}),
                    isCollected=bool(all_classes & {"collected", "done", "checked"})
                    or box.select_one("img.achievementCheck, .collected") is not None,
                )
            )

        self._fountain_response = resp

    async def collect(self) -> AjaxResponse:
        """Collect today's Ambrosia from the active Divine Ambrosia Fountain."""
        ...

    async def activate(self) -> AjaxResponse:
        """Activate the Divine Ambrosia Fountain using Ambrosia."""
        ...

    async def extend(self) -> AjaxResponse:
        """Extend the active Divine Ambrosia Fountain duration using Ambrosia."""
        ...


class ShopView:
    """View model for the city Flying Trader / Shop overlay."""

    city: Optional[City]
    shopHref: Optional[str]
    iframeUrl: Optional[str]

    def __init__(
        self,
        viewData: Union[str, AjaxResponse],
        city: Optional[City] = None,
        shopHref: Optional[str] = None,
    ) -> None:
        """Parse the external shop iframe URL from the Flying Trader view."""
        self.city = city
        self.shopHref = shopHref
        resp, soup = parse_view_payload(viewData)
        iframe = soup.select_one("#zShopIFrame")
        self.iframeUrl = str(iframe["src"]) if iframe and iframe.get("src") else None
        self._shop_response = resp


class IslandCityView:
    """Possible actions and player details shown in the ``cityDetails`` sidebar."""

    targetCity: "IslandCity"
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

    def __init__(self, city: "IslandCity", data: dict) -> None:
        """Parse city details and available actions from ``updateTemplateData``."""
        self.targetCity = city

        title_html = (data.get("js_selectedCityOwnerTitle") or {}).get("text") or ""
        self.ownerTitle = make_soup(title_html).get_text(strip=True) or None

        owner_html = (data.get("js_selectedCityOwnerName") or {}).get("text") or ""
        flag_span = make_soup(owner_html).select_one("span.flag")
        self.ownerFlagTag = (
            next((cls for cls in (flag_span.get("class") or []) if cls != "flag"), None)
            if flag_span
            else None
        )

        self.totalScore = parse_int((data.get("js_selectedCityScore") or {}).get("text")) or 0
        spies_entry = data.get("js_selectedCityActiveSpies")
        self.hasSpies = isinstance(spies_entry, dict) and spies_entry.get("class") != "invisible"

        for _, attr_name in _ACTION_HREF_FLAGS:
            setattr(self, attr_name, False)

        for row in data.values():
            if not isinstance(row, dict) or "href" not in row or row.get("class") == "invisible":
                continue
            href = row.get("href") or ""
            view_name = parse_query_str(href, "view")
            for key, attr_name in _ACTION_HREF_FLAGS:
                if (view_name == key) if view_name else (key in href):
                    setattr(self, attr_name, True)
                    break

        self.__island_city_actions_data = data

    async def _open_mission_view(self, view: str) -> str:
        """Fetch an island city mission view HTML payload via ``post_ajax``."""
        resp = await self.targetCity._client.post_ajax(
            params={
                "view": view,
                "isMission": "1",
                "destinationCityId": str(self.targetCity.id),
                "backgroundView": "island",
                "currentIslandId": str(self.targetCity.island.id),
                "templateView": view,
                "actionRequest": "REQUESTID",
                "ajax": "1",
            }
        )
        if not resp.view_html:
            feedback = "; ".join(
                str(item.get("text", ""))
                for item in resp.feedback
                if isinstance(item, dict) and item.get("text")
            )
            detail = f": {feedback}" if feedback else ""
            raise ValueError(
                f"Could not open {view!r} view for city {self.targetCity.id}{detail}"
            )
        return resp.view_html

    async def sendMessage(
        self,
        body: str,
        *,
        subject: str = "",
        msgType: str = "50",
    ) -> AjaxResponse:
        """Send a personal diplomatic message or treaty request to the city owner."""
        from ikabot.ikariam.advisors import execute_send_ik_message

        if not self.targetCity.ownerId:
            raise ValueError(f"City {self.targetCity.id} has no ownerId")
        return await execute_send_ik_message(
            self.targetCity._client,
            self.targetCity.ownerId,
            body,
            subject=subject,
            msg_type=msgType,
            current_island_id=self.targetCity.island.id,
            action_name="IslandCityView.sendMessage",
        )

    async def reportPlayer(self) -> None:
        """Report the city owner to a game operator."""
        ...

    async def sendMessageAlliance(self) -> None:
        """Open or send a message to the city owner's alliance."""
        ...

    async def _open_origin_mission_view(
        self,
        view: str,
        originCityId: Optional[int] = None,
    ) -> Tuple[str, Optional[int]]:
        """Optionally switch to ``originCityId`` before opening a mission view."""
        client = self.targetCity._client
        if originCityId is not None:
            await _select_city_id(
                client,
                int(originCityId),
                action_name=f"IslandCityView.{view}",
            )
            resolved_origin: Optional[int] = int(originCityId)
        elif client.selectedDropDownCity is not None:
            resolved_origin = client.selectedDropDownCity.id
        else:
            resolved_origin = None
        return await self._open_mission_view(view), resolved_origin

    async def transportGoods(self, *, originCityId: Optional[int] = None) -> TransportView:
        """Open the transport goods view targeting this city."""
        html, origin_id = await self._open_origin_mission_view("transport", originCityId)
        return TransportView(
            html,
            client=self.targetCity._client,
            originCityId=origin_id,
        )

    async def defendCity(self, *, originCityId: Optional[int] = None) -> SendUnitsView:
        """Open the defend town mission view targeting this city."""
        html, origin_id = await self._open_origin_mission_view("defendCity", originCityId)
        return SendUnitsView(
            html,
            client=self.targetCity._client,
            originCityId=origin_id,
        )

    async def defendPort(self, *, originCityId: Optional[int] = None) -> SendUnitsView:
        """Open the defend port mission view targeting this city."""
        html, origin_id = await self._open_origin_mission_view("defendPort", originCityId)
        return SendUnitsView(
            html,
            client=self.targetCity._client,
            originCityId=origin_id,
        )

    async def pillage(self, *, originCityId: Optional[int] = None) -> SendUnitsView:
        """Open the pillage mission view targeting this city."""
        html, origin_id = await self._open_origin_mission_view("plunder", originCityId)
        return SendUnitsView(
            html,
            client=self.targetCity._client,
            originCityId=origin_id,
        )

    async def piracyRaid(self, *, originCityId: Optional[int] = None) -> AjaxResponse:
        """Launch a pirate fortress raid targeting this city."""
        from ikabot.ikariam.buildings.pirate_fortress import execute_piracy_raid

        return await execute_piracy_raid(
            self.targetCity._client,
            self.targetCity.id,
            origin_city_id=originCityId,
            current_island_id=self.targetCity.island.id,
            action_name="IslandCityView.piracyRaid",
        )

    async def occupyPort(self) -> None:
        """Open the port blockade mission view targeting this city."""
        ...

    async def occupyCity(self) -> None:
        """Open the city occupation mission view targeting this city."""
        ...

    async def sendSpy(
        self,
        *,
        originCityId: Optional[int] = None,
        agents: int = 1,
        decoys: int = 0,
    ) -> AjaxResponse:
        """Dispatch spies from ``originCityId`` (or active city) to this city."""
        from ikabot.ikariam.buildings.safehouse import execute_send_spy

        return await execute_send_spy(
            self.targetCity._client,
            self.targetCity.id,
            origin_city_id=originCityId,
            current_island_id=self.targetCity.island.id,
            agents=agents,
            decoys=decoys,
            action_name="IslandCityView.sendSpy",
        )


class _Occupier:
    """Shared base for city and port occupation metadata on an island spot."""

    islandCity: "IslandCity"
    id: int
    name: str
    allianceTag: Optional[str]
    isForeign: bool

    def __init__(
        self,
        islandCity: "IslandCity",
        data: dict,
        *,
        tag_source: str,
        strip_bracket_from_name: bool,
    ) -> None:
        self.islandCity = islandCity
        self.id = parse_int(data.get("id")) or 0
        raw_name = decode_unicode_escape(data.get("name"))
        if strip_bracket_from_name and "[" in raw_name:
            self.name = raw_name.split("[", 1)[0].strip()
        else:
            self.name = raw_name
        self.allianceTag = _extract_alliance_tag(tag_source)
        self.isForeign = data.get("color") == "foreignBlocker"


class PortOccupier(_Occupier):
    """Information about a player currently blockading a city's port."""

    def __init__(self, islandCity: "IslandCity", data: dict) -> None:
        """Initialize port occupier details from ``infos['fleetAction']``."""
        raw_name = decode_unicode_escape(data.get("name"))
        super().__init__(
            islandCity,
            data,
            tag_source=raw_name,
            strip_bracket_from_name=True,
        )
        self.__port_occupier_data = data


class CityOccupier(_Occupier):
    """Information about a player currently occupying a city by land."""

    def __init__(self, islandCity: "IslandCity", data: dict) -> None:
        """Initialize city occupier details from ``infos['occupation']``."""
        tooltip = decode_unicode_escape(data.get("tooltip"))
        super().__init__(
            islandCity,
            data,
            tag_source=tooltip,
            strip_bracket_from_name=False,
        )
        self.__city_occupier_data = data


class IslandPlace:
    """Empty building spot on an island."""

    island: "Island"
    position: int
    name: str
    isPremiumSpot: bool

    def __init__(self, island: "Island", position: int, data: dict) -> None:
        """Initialize an empty island buildplace."""
        self.island = island
        self.position = position
        self.name = decode_unicode_escape(data.get("name")) or "Building ground"
        self.isPremiumSpot = data.get("buildplace_type") == "premium"
        self.__island_place_data = data

    async def colonize(self) -> None:
        """Open or initiate colonization on this empty island spot."""
        ...


class IslandCity(IslandPlace, DropdownCity):
    """City located on an island view, supporting island and city operations."""

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
    isPlagued: bool
    viewableLevel: int
    isPiracyRaidable: bool
    portOccupier: Optional[PortOccupier]
    cityOccupier: Optional[CityOccupier]
    avatarScore: Optional[AvatarScore]

    def __init__(self, island: "Island", position: int, data: dict) -> None:
        """Initialize an island city from an island ``cities`` entry."""
        IslandPlace.__init__(
            self,
            island,
            position,
            {"buildplace_type": "premium" if position == 16 else "not premium"},
        )
        client = (
            island._client
            if hasattr(island, "_client")
            else getattr(island, "_Island__client", None)
        )
        self._client = client

        self.name = decode_unicode_escape(data.get("name"))
        self.id = parse_int(data.get("id")) or 0
        self.x = island.x
        self.y = island.y
        self.luxuryResourceType = island.luxuryResourceType
        self.luxuryResourceName = island.luxuryResourceName
        self.ownerId = parse_int(data.get("ownerId")) or 0
        user_id = parse_int(getattr(client, "userId", None))
        self.isOwnCity = user_id is not None and self.ownerId == user_id
        self.level = parse_int(data.get("level")) or 0
        self.ownerName = decode_unicode_escape(data.get("ownerName"))

        ally_id = parse_int(data.get("ownerAllyId"))
        self.ownerAllianceId = ally_id if ally_id else None
        raw_ally_tag = data.get("ownerAllyTag")
        self.ownerAllianceTag = (
            decode_unicode_escape(raw_ally_tag)
            if self.ownerAllianceId and raw_ally_tag
            else None
        )

        self.hasTreaties = bool(data.get("hasTreaties"))
        state = data.get("state", data.get("status", ""))
        self.isInactive = state == "inactive"
        self.isVacation = state == "vacation"
        self.isGodlyProtection = state == "noob"
        self.isBanned = state == "inactive_banned"

        raw_infos = data.get("infos")
        infos = raw_infos if isinstance(raw_infos, dict) else {}
        self.isFighting = infos.get("armyAction") == "fight"
        self.isPlagued = bool(data.get("infestedByPlague", False))
        self.viewableLevel = parse_int(data.get("viewAble")) or 0
        self.isPiracyRaidable = "piracy_raid" in (data.get("actions") or [])

        self.portOccupier = (
            PortOccupier(self, infos["fleetAction"])
            if infos.get("fleetAction")
            else None
        )
        self.cityOccupier = (
            CityOccupier(self, infos["occupation"])
            if infos.get("occupation")
            else None
        )
        self.avatarScore = next(
            (
                avatar_score
                for avatar_score in self.island.avatarScores
                if avatar_score.userId == self.ownerId
            ),
            None,
        )
        self.__island_city_data = data

    async def selectCity(self) -> Optional[City]:
        """Select this city as the active city if owned by the current player."""
        if self.isOwnCity:
            return await super().selectCity()
        return None

    async def colonize(self) -> None:
        """No-op because an existing city spot cannot be colonized."""
        return None

    async def getActions(self) -> IslandCityView:
        """Fetch and return available actions and details for this city."""
        resp = await self._client.post_ajax(
            params={
                "view": "cityDetails",
                "isMission": "1",
                "destinationCityId": str(self.id),
                "backgroundView": "island",
                "currentIslandId": str(self.island.id),
                "templateView": "cityDetails",
                "actionRequest": "REQUESTID",
                "ajax": "1",
            }
        )
        return IslandCityView(self, resp.template_data)

    async def getPlayer(self) -> Optional[PlayerHighScoreTableRow]:
        """Fetch highscore player metadata for this city's owner."""
        if not self.ownerName:
            return None
        hs = await self._client.getPlayerHighScoreView(
            showMe=False,
            searchUser=self.ownerName,
        )
        for row in hs.playerHighScoreTable.rows:
            if self.ownerId and row.playerId == self.ownerId:
                return row
        for row in hs.playerHighScoreTable.rows:
            if row.playerName == self.ownerName:
                return row
        return hs.playerHighScoreTable.rows[0] if len(hs.playerHighScoreTable.rows) == 1 else None
