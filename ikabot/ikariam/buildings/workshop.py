"""Workshop building model (`view=workshop`, `buildingId=15`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_int,
    parse_query_int,
    parse_query_params,
    parse_query_str,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_duration_seconds,
    parse_view_payload,
    strip_hidden_text,
)
from ikabot.ikariam.data import Resources, Unit, Units

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


_NEXT_LEVEL_RE = re.compile(r"Next\s+Level:\s*(.+?)\s*\((\d+)\)\s*$", re.IGNORECASE)
_EFFECT_ARROW_RE = re.compile(
    r"^\s*(.+?)\s+([+-]?\d+)\s*(?:⇒|->|=>|&DoubleRightArrow;)\s*([+-]?\d+)\s*$"
)
_NUMBER_TOKEN_RE = re.compile(r"(\d[\d,.\s\xa0]*)")
_WORKSHOP_TEXT_CLEAN_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    """Collapse internal whitespace cleanly."""
    return _WORKSHOP_TEXT_CLEAN_RE.sub(" ", str(value or "")).strip()


def _parse_workshop_cost_li(li_tag: Optional[Tag]) -> int:
    """Extract an exact integer cost from a Workshop resource ``<li>``.

    Workshop cards display abbreviated values such as ``4.69M`` in the inner
    text while putting the exact comma-formatted figure inside ``title``
    (for example ``"Costs: 4,691,655 Gold"``).
    """
    if li_tag is None:
        return 0
    title = li_tag.get("title")
    if title:
        match = _NUMBER_TOKEN_RE.search(str(title))
        if match:
            val = parse_int(match.group(1))
            if val is not None:
                return val
    text = strip_hidden_text(li_tag)
    val = parse_int(text)
    return val if val is not None else 0


def _parse_effect_line(text: str) -> Tuple[str, str, str]:
    """Parse ``'Damage +15 ⇒ +20'`` into ``(statName, currentBonus, nextBonus)``."""
    cleaned = _clean_text(text)
    match = _EFFECT_ARROW_RE.match(cleaned)
    if match:
        return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
    return cleaned, "", ""


@dataclass
class WorkshopUpgradeOption:
    """Single upgrade track (``offensive``, ``defensive``, or ``cargo``) for a unit/ship."""

    unitId: int
    upgradeType: str
    upgradeTypeName: str = ""
    upgradeTypeDesc: str = ""
    currentName: str = ""
    currentLevel: int = 0
    currentEffect: str = ""
    nextName: str = ""
    nextLevel: int = 0
    nextEffect: str = ""
    statName: str = ""
    currentBonus: str = ""
    nextBonus: str = ""
    cost: Resources = field(default_factory=Resources)
    durationSeconds: Optional[int] = None
    durationText: str = ""
    canUpgrade: bool = False
    errorText: Optional[str] = None
    actionUrl: Optional[str] = None


@dataclass
class WorkshopUnitEntry:
    """All Workshop upgrade tracks for a single troop or warship type."""

    unitId: int
    unitName: str
    unit: Optional[Unit] = None
    upgrades: Dict[str, WorkshopUpgradeOption] = field(default_factory=dict)

    @property
    def offensive(self) -> Optional[WorkshopUpgradeOption]:
        """Offensive weapon/attack upgrade track, if applicable."""
        return self.upgrades.get("offensive")

    @property
    def defensive(self) -> Optional[WorkshopUpgradeOption]:
        """Defensive armour/shield upgrade track, if applicable."""
        return self.upgrades.get("defensive")

    @property
    def cargo(self) -> Optional[WorkshopUpgradeOption]:
        """Cargo capacity upgrade track (Merchant Ships / Freighter), if applicable."""
        return self.upgrades.get("cargo")


class Workshop(Building):
    """Ikariam Workshop building model (``view=workshop``).

    Supports both the land units tab (``activeTab=tabUnits``, default) and the
    ships tab (``activeTab=tabShips``).
    """

    buildingId: int = 15
    buildingType: str = "workshop"

    def __init__(
        self,
        client: Optional["IkariamClient"] = None,
        city: Optional["City"] = None,
        cityId: Optional[int] = None,
        position: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        self.activeTab: str = "tabUnits"
        self.unitUpgrades: List[WorkshopUnitEntry] = []
        self.shipUpgrades: List[WorkshopUnitEntry] = []
        self.inProgressUpgrade: Optional[Dict[str, Any]] = None
        self.visibleUnitIds: List[int] = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse the active Workshop tab returned by ``view=workshop``."""
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        tmpl_tab = tmpl.get("activeTab")
        in_progress = tmpl.get("inProgress")
        self.inProgressUpgrade = dict(in_progress) if isinstance(in_progress, dict) else None

        visible_ids = tmpl.get("listOfVisibleUnits")
        if isinstance(visible_ids, list):
            parsed_ids = [parse_int(uid) for uid in visible_ids]
            self.visibleUnitIds = [uid for uid in parsed_ids if uid is not None]

        has_ships = soup.select_one("#tabShips") is not None
        has_units = soup.select_one("#tabUnits") is not None

        if tmpl_tab == "tabShips" or (has_ships and not has_units):
            self.activeTab = "tabShips"
            self.shipUpgrades = self._parse_upgrade_tab(soup, resp, tab_id="tabShips")
        else:
            self.activeTab = str(tmpl_tab or "tabUnits")
            if has_units or not has_ships:
                self.unitUpgrades = self._parse_upgrade_tab(soup, resp, tab_id="tabUnits")
            if has_ships:
                self.shipUpgrades = self._parse_upgrade_tab(soup, resp, tab_id="tabShips")

    def parseUnits(self, viewData: Union[str, AjaxResponse]) -> "Workshop":
        """Parse the ``tabUnits`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabUnits"
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        if "inProgress" in tmpl:
            in_progress = tmpl.get("inProgress")
            self.inProgressUpgrade = dict(in_progress) if isinstance(in_progress, dict) else None
        self.unitUpgrades = self._parse_upgrade_tab(soup, resp, tab_id="tabUnits")
        return self

    def parseShips(self, viewData: Union[str, AjaxResponse]) -> "Workshop":
        """Parse the ``tabShips`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabShips"
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        if "inProgress" in tmpl:
            in_progress = tmpl.get("inProgress")
            self.inProgressUpgrade = dict(in_progress) if isinstance(in_progress, dict) else None
        self.shipUpgrades = self._parse_upgrade_tab(soup, resp, tab_id="tabShips")
        return self

    async def loadUnits(self) -> "Workshop":
        """Fetch and parse ``activeTab=tabUnits``."""
        resp = await self._fetch_view(view="workshop", activeTab="tabUnits")
        return self.parseUnits(resp)

    async def loadShips(self) -> "Workshop":
        """Fetch and parse ``activeTab=tabShips``."""
        resp = await self._fetch_view(view="workshop", activeTab="tabShips")
        return self.parseShips(resp)

    async def loadAllTabs(self) -> "Workshop":
        """Refresh the primary view and the ships tab."""
        await self.load()
        await self.loadShips()
        return self

    def getUnit(self, unitOrId: Union[int, str, Unit]) -> Optional[WorkshopUnitEntry]:
        """Look up a unit or ship upgrade entry by ID, ``Unit``, or name."""
        target_id: Optional[int] = None
        target_name: Optional[str] = None
        if isinstance(unitOrId, Unit):
            target_id = unitOrId.id
            target_name = unitOrId.name.lower()
        elif isinstance(unitOrId, int):
            target_id = unitOrId
        else:
            parsed_id = parse_int(unitOrId)
            if parsed_id is not None and str(parsed_id) == str(unitOrId).strip():
                target_id = parsed_id
            else:
                target_name = str(unitOrId).strip().lower()

        for entry in (*self.unitUpgrades, *self.shipUpgrades):
            if target_id is not None and entry.unitId == target_id:
                return entry
            if target_name is not None and entry.unitName.lower() == target_name:
                return entry
        return None

    def _parse_upgrade_tab(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        *,
        tab_id: str,
    ) -> List[WorkshopUnitEntry]:
        """Parse all ``.units`` cards inside ``#<tab_id>`` using HTML + ``completeData``."""
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        complete_data = tmpl.get("completeData")
        if not isinstance(complete_data, dict):
            complete_data = {}

        container = soup.select_one(f"#{tab_id}") or soup
        rows = container.select("div.units")
        entries: List[WorkshopUnitEntry] = []

        for row in rows:
            entry = self._parse_unit_row(row, complete_data)
            if entry is not None:
                entries.append(entry)

        if not entries and complete_data:
            for raw_uid, tracks in complete_data.items():
                uid = parse_int(raw_uid)
                if uid is None or not isinstance(tracks, dict):
                    continue
                unit_obj = Units.getUnitById(uid)
                entry_name = unit_obj.name if unit_obj is not None else f"Unit {uid}"
                upgrades: Dict[str, WorkshopUpgradeOption] = {}
                for track_key, track_data in tracks.items():
                    if isinstance(track_data, dict):
                        upgrades[track_key] = self._option_from_template(uid, track_key, track_data)
                entries.append(
                    WorkshopUnitEntry(
                        unitId=uid,
                        unitName=entry_name,
                        unit=unit_obj,
                        upgrades=upgrades,
                    )
                )

        return entries

    def _parse_unit_row(
        self,
        row: Tag,
        complete_data: Dict[str, Any],
    ) -> Optional[WorkshopUnitEntry]:
        """Parse a single ``div.units`` row containing 1 or 2 upgrade boxes."""
        display = row.select_one(".unitDisplay")
        unit_name = _clean_text(display.get("title", "")) if display else ""

        unit_id: Optional[int] = None
        for link in row.select(".highlightbox a.button[href]"):
            uid = parse_query_int(link.get("href"), "unitId")
            if uid is not None:
                unit_id = uid
                break

        unit_obj: Optional[Unit] = None
        if unit_id is not None:
            unit_obj = Units.getUnitById(unit_id)
        elif unit_name:
            unit_obj = Units.getUnitByName(unit_name)
            if unit_obj is not None:
                unit_id = unit_obj.id

        if unit_id is None:
            return None
        if not unit_name and unit_obj is not None:
            unit_name = unit_obj.name

        unit_complete = complete_data.get(str(unit_id))
        if not isinstance(unit_complete, dict):
            unit_complete = {}

        upgrades: Dict[str, WorkshopUpgradeOption] = {}
        boxes = row.select(".highlightbox")
        fallback_types = ["cargo"] if unit_id in (201, 204) else ["offensive", "defensive"]

        for idx, box in enumerate(boxes):
            button = box.select_one("a.button[href]")
            href = button.get("href") if button else None
            upgrade_type = parse_query_str(href, "upgradeType") if href else None
            if not upgrade_type:
                upgrade_type = (
                    fallback_types[idx] if idx < len(fallback_types) else f"track_{idx}"
                )

            track_data = unit_complete.get(upgrade_type)
            option = self._parse_upgrade_box(
                unit_id=unit_id,
                upgrade_type=upgrade_type,
                box=box,
                track_data=track_data if isinstance(track_data, dict) else None,
            )
            upgrades[upgrade_type] = option

        return WorkshopUnitEntry(
            unitId=unit_id,
            unitName=unit_name,
            unit=unit_obj,
            upgrades=upgrades,
        )

    def _option_from_template(
        self,
        unit_id: int,
        upgrade_type: str,
        track_data: Dict[str, Any],
    ) -> WorkshopUpgradeOption:
        """Build a ``WorkshopUpgradeOption`` solely from ``completeData`` JSON."""
        option = WorkshopUpgradeOption(unitId=unit_id, upgradeType=upgrade_type)
        self._merge_template_track(option, track_data)
        return option

    def _merge_template_track(
        self,
        option: WorkshopUpgradeOption,
        track_data: Dict[str, Any],
    ) -> None:
        """Populate/enrich an option with Ikariam ``completeData`` metadata."""
        option.upgradeTypeName = _clean_text(track_data.get("upgradeTypeName"))
        option.upgradeTypeDesc = _clean_text(track_data.get("upgradeTypeDesc"))
        err = _clean_text(track_data.get("errorText"))
        if err:
            option.errorText = err

        curr = track_data.get("currentLevel")
        if isinstance(curr, dict):
            curr_lvl = parse_int(curr.get("upgradeLevel"))
            if curr_lvl is not None:
                option.currentLevel = curr_lvl
            curr_name = _clean_text(curr.get("upgradeName"))
            if curr_name:
                option.currentName = curr_name
            curr_eff = _clean_text(curr.get("upgradeEffect"))
            if curr_eff:
                option.currentEffect = curr_eff

        nxt = track_data.get("nextLevel")
        if isinstance(nxt, dict):
            nxt_lvl = parse_int(nxt.get("upgradeLevel"))
            if nxt_lvl is not None:
                option.nextLevel = nxt_lvl
            nxt_name = _clean_text(nxt.get("upgradeName"))
            if nxt_name:
                option.nextName = nxt_name
            nxt_eff = _clean_text(nxt.get("upgradeEffect"))
            if nxt_eff:
                option.nextEffect = nxt_eff

            gold_cost = parse_int(nxt.get("goldCosts"))
            crystal_cost = parse_int(nxt.get("crystalCosts"))
            if gold_cost is not None or crystal_cost is not None:
                option.cost = Resources(
                    gold=gold_cost if gold_cost is not None else option.cost.Gold.count,
                    crystal=(
                        crystal_cost if crystal_cost is not None else option.cost.Crystal.count
                    ),
                )

            dur_text = _clean_text(nxt.get("duration"))
            if dur_text:
                option.durationText = dur_text
                parsed_dur = parse_duration_seconds(dur_text)
                if parsed_dur is not None:
                    option.durationSeconds = parsed_dur

    def _parse_upgrade_box(
        self,
        *,
        unit_id: int,
        upgrade_type: str,
        box: Tag,
        track_data: Optional[Dict[str, Any]],
    ) -> WorkshopUpgradeOption:
        """Parse one ``.highlightbox`` card and merge any ``completeData`` values."""
        option = WorkshopUpgradeOption(unitId=unit_id, upgradeType=upgrade_type)

        action_div = box.select_one("div.actionButton")
        button = action_div.select_one("a.button[href]") if action_div else None
        error_p = box.select_one("p.actionButton.red")

        action_div_classes = action_div.get("class", []) if action_div else []
        error_p_classes = error_p.get("class", []) if error_p else []
        error_p_text = _clean_text(error_p.get_text(" ", strip=True)) if error_p else ""

        option.actionUrl = button.get("href") if button else None
        if error_p_text and "invisible" not in error_p_classes:
            option.errorText = error_p_text
            option.canUpgrade = False
        elif button is not None and "invisible" not in action_div_classes:
            option.canUpgrade = True

        desc_div = box.select_one(".upgrade_desc")
        if desc_div is not None:
            effect_p = desc_div.select_one("p.smallFont")
            effect_text = _clean_text(effect_p.get_text(" ", strip=True)) if effect_p else ""
            if effect_text:
                stat_name, curr_bonus, next_bonus = _parse_effect_line(effect_text)
                option.statName = stat_name
                option.currentBonus = curr_bonus
                option.nextBonus = next_bonus

            heading_parts = [
                str(child)
                for child in desc_div.contents
                if isinstance(child, str)
            ]
            heading_text = _clean_text(" ".join(heading_parts))
            lvl_match = _NEXT_LEVEL_RE.search(heading_text)
            if lvl_match:
                option.nextName = _clean_text(lvl_match.group(1))
                next_lvl = parse_int(lvl_match.group(2))
                if next_lvl is not None:
                    option.nextLevel = next_lvl
                    if next_lvl > 0:
                        option.currentLevel = next_lvl - 1

        res_ul = box.select_one("ul.resources")
        if res_ul is not None:
            gold_li = res_ul.select_one("li.gold")
            glass_li = res_ul.select_one("li.glass")
            time_li = res_ul.select_one("li.time")

            option.cost = Resources(
                gold=_parse_workshop_cost_li(gold_li),
                crystal=_parse_workshop_cost_li(glass_li),
            )
            if time_li is not None:
                dur_src = time_li.get("title") or strip_hidden_text(time_li)
                dur_clean = _clean_text(dur_src)
                if dur_clean.lower().startswith("duration:"):
                    dur_clean = _clean_text(dur_clean.split(":", 1)[1])
                option.durationText = dur_clean
                option.durationSeconds = parse_duration_seconds(dur_clean)

        if not option.nextName:
            img = box.select_one("img.newImage[alt]")
            if img and img.get("alt"):
                option.nextName = _clean_text(img.get("alt"))

        if track_data:
            self._merge_template_track(option, track_data)

        if option.errorText and "invisible" not in error_p_classes:
            option.canUpgrade = False

        return option

    async def _start_upgrade(
        self,
        *,
        tab: str,
        unitOrId: Union[int, str, Unit],
        upgradeType: str,
        actionName: str,
    ) -> "Workshop":
        """Validate and submit a Workshop unit or ship upgrade request."""
        entries = self.unitUpgrades if tab == "tabUnits" else self.shipUpgrades
        if not self.isLoaded or not entries:
            await (self.loadUnits() if tab == "tabUnits" else self.loadShips())
            entries = self.unitUpgrades if tab == "tabUnits" else self.shipUpgrades

        if self.inProgressUpgrade:
            raise ValueError(
                f"Workshop@{self.cityId} already has an upgrade in progress"
            )

        entry = self.getUnit(unitOrId)
        if entry is None or entry not in entries:
            raise ValueError(
                f"No Workshop entry on {tab} matching {unitOrId!r} in city {self.cityId}"
            )

        option = entry.upgrades.get(upgradeType)
        if option is None:
            available = ", ".join(sorted(entry.upgrades.keys())) or "none"
            raise ValueError(
                f"No {upgradeType!r} upgrade track for {entry.unitName} (available: {available})"
            )
        if not option.canUpgrade:
            raise ValueError(
                option.errorText
                or f"Cannot upgrade {entry.unitName} ({upgradeType}) in city {self.cityId}"
            )

        params = (
            parse_query_params(option.actionUrl)
            if option.actionUrl
            else {
                "action": "StartWorkshopUpgrade",
                "cityId": str(self.cityId),
                "position": str(self.position),
                "unitId": str(entry.unitId),
                "upgradeType": upgradeType,
            }
        )
        params.update(
            {
                "activeTab": tab,
                "backgroundView": "city",
                "currentCityId": str(self.cityId),
                "templateView": "workshop",
                "actionRequest": "REQUESTID",
                "ajax": "1",
            }
        )

        client = self._require_client()
        resp = await client.post_action(
            params=params,
            metadata={
                "ambrosia_cost": 0,
                "cityId": self.cityId,
                "unitId": entry.unitId,
                "upgradeType": upgradeType,
            },
            action_name=actionName,
        )
        if resp.view_html and ("tabUnits" in resp.view_html or "tabShips" in resp.view_html):
            if tab == "tabUnits":
                self.parseUnits(resp)
            else:
                self.parseShips(resp)
        else:
            await (self.loadUnits() if tab == "tabUnits" else self.loadShips())
        return self

    async def upgradeUnit(
        self,
        unitOrId: Union[int, str, Unit],
        upgradeType: str = "offensive",
    ) -> "Workshop":
        """Start a Workshop troop upgrade on the land units tab."""
        return await self._start_upgrade(
            tab="tabUnits",
            unitOrId=unitOrId,
            upgradeType=upgradeType,
            actionName="Workshop.upgradeUnit",
        )

    async def upgradeShip(
        self,
        unitOrId: Union[int, str, Unit],
        upgradeType: str = "offensive",
    ) -> "Workshop":
        """Start a Workshop warship or cargo ship upgrade on the ships tab."""
        return await self._start_upgrade(
            tab="tabShips",
            unitOrId=unitOrId,
            upgradeType=upgradeType,
            actionName="Workshop.upgradeShip",
        )
