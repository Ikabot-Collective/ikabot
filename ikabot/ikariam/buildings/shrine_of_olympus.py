"""Shrine of Olympus (Gods' Shrine) building model (`view=shrineOfOlympus`, `buildingId=34`)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import AjaxResponse, parse_float, parse_int
from ikabot.ikariam.buildings._base import (
    Building,
    parse_duration_seconds,
    parse_view_payload,
    tmpl_int,
    tmpl_value,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


_STYLE_WIDTH_RE = re.compile(r"width\s*:\s*([0-9.]+)\s*%", re.IGNORECASE)
_INT_TOKEN_RE = re.compile(r"(\d[\d,.]*)")
_SWITCH_TAB_RE = re.compile(r'switchTab\(["\']([^"\']+)["\']\)')
_WS_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    """Collapse internal whitespace cleanly."""
    return _WS_RE.sub(" ", str(value or "")).strip()


def _parse_load_js_params(resp: AjaxResponse) -> Dict[str, Any]:
    """Extract parsed JSON dict from ``resp.template_data['load_js']['params']``."""
    tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
    load_js = tmpl.get("load_js")
    if not isinstance(load_js, dict):
        return {}
    raw = load_js.get("params")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw, strict=False)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tmpl_lookup(tmpl: Dict[str, Any], *keys: str) -> Any:
    """Return the first matching selector key value from ``template_data``."""
    for key in keys:
        if key in tmpl:
            return tmpl[key]
    return None


@dataclass
class ShrineItemInfo:
    """Fleece shop item offered for extending a god's grace period."""

    itemId: int
    name: str
    price: int = 0
    durationSeconds: Optional[int] = None
    hasItem: int = 0
    cssClass: str = ""


@dataclass
class ShrineGodStatus:
    """Status entry for one Olympian deity in ``#tabOverview``."""

    godId: int
    slug: str
    name: str
    isWorshipped: bool = False
    isResearched: bool = True
    isBuildingLevelMet: bool = True
    gracePeriodText: str = ""
    gracePeriodSeconds: Optional[int] = None
    favorDonated: int = 0
    favorMax: int = 1000
    favorPercent: Optional[float] = None
    canDonate: bool = True
    canExtendGrace: bool = False
    researchRequirement: str = ""
    buildingRequirement: str = ""


@dataclass
class ShrineWorshipSlot:
    """City-to-god worship assignment slot in ``#tabWorship``."""

    slotNumber: int
    cityId: Optional[int] = None
    cityName: Optional[str] = None
    godId: Optional[int] = None
    godName: Optional[str] = None
    startTime: Optional[str] = None
    generatedResources: Optional[int] = None
    currentBonusPercent: Optional[float] = None


class ShrineOfOlympus(Building):
    """Ikariam Gods' Shrine / Shrine of Olympus model (``view=shrineOfOlympus``).

    Both ``#tabOverview`` (6 gods & favour progress) and ``#tabWorship``
    (empire city-to-god assignment slots) are rendered inline in the primary
    response, with live progress/bonus values supplied in ``template_data``.
    """

    buildingId: int = 34
    buildingType: str = "shrineOfOlympus"

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
        self.activeTab: str = "tabOverview"
        self.currentFavor: int = 0
        self.isMaxLevelReached: bool = False
        self.maximumBonusNextLevel: Optional[int] = None
        self.numberOfCitiesPossibleNextLevel: Optional[int] = None
        self.numberOfAdditionalCitiesPossible: Optional[int] = None
        self.researchedGodIds: List[int] = []
        self.items: Dict[int, ShrineItemInfo] = {}
        self.gods: List[ShrineGodStatus] = []
        self.worshipSlots: List[ShrineWorshipSlot] = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse favor balance, sidebar caps, overview gods, and worship slots."""
        params = _parse_load_js_params(resp)
        for script in soup.select("#mainview script"):
            m = _SWITCH_TAB_RE.search(script.get_text(" "))
            if m:
                self.activeTab = m.group(1)
                break

        self._parse_header_and_metadata(soup, resp, params)
        self._parse_worship_dom(soup, resp)
        self._parse_overview_dom(soup, resp, params)

    def _parse_header_and_metadata(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        params: Dict[str, Any],
    ) -> None:
        """Parse current favor, next-level limits, researched gods, and fleece items."""
        favor = tmpl_int(resp, "currentFavor")
        if favor is None:
            favor_el = soup.select_one("#currentFavor")
            favor = parse_int(favor_el.get_text(" ", strip=True)) if favor_el else None
        self.currentFavor = favor if favor is not None else 0

        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        self.isMaxLevelReached = bool(tmpl.get("isMaxLevelReached", False))
        self.maximumBonusNextLevel = parse_int(tmpl.get("maximumBonusNextLvl"))
        self.numberOfCitiesPossibleNextLevel = parse_int(
            tmpl.get("numberOfCitiesPossibleNextLvl")
        )
        self.numberOfAdditionalCitiesPossible = parse_int(
            tmpl.get("numberOfAdditionalCitiesPossible")
        )

        sidebar = soup.select_one("#informationSidebar")
        if sidebar is not None:
            for p in sidebar.select("p"):
                txt = _clean_text(p.get_text(" ", strip=True)).lower()
                m_val = _INT_TOKEN_RE.search(txt)
                val = parse_int(m_val.group(1)) if m_val else None
                if val is None:
                    continue
                if "maximum blessing" in txt and self.maximumBonusNextLevel is None:
                    self.maximumBonusNextLevel = val
                elif "maximum number of towns" in txt and self.numberOfCitiesPossibleNextLevel is None:
                    self.numberOfCitiesPossibleNextLevel = val

        raw_researched = tmpl.get("researchedGods")
        if isinstance(raw_researched, list):
            self.researchedGodIds = [
                gid for gid in (parse_int(x) for x in raw_researched) if gid is not None
            ]

        raw_items = tmpl.get("itemData") or params.get("itemData")
        if isinstance(raw_items, dict):
            parsed_items: Dict[int, ShrineItemInfo] = {}
            for raw_id, info in raw_items.items():
                item_id = parse_int(raw_id)
                if item_id is None or not isinstance(info, dict):
                    continue
                parsed_items[item_id] = ShrineItemInfo(
                    itemId=item_id,
                    name=_clean_text(info.get("name")),
                    price=parse_int(info.get("price")) or 0,
                    durationSeconds=parse_int(info.get("duration")),
                    hasItem=parse_int(info.get("hasItem")) or 0,
                    cssClass=_clean_text(info.get("cssClass")),
                )
            self.items = parsed_items

    def _parse_overview_dom(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        params: Dict[str, Any],
    ) -> None:
        """Parse `#tabOverview ul.gods.overview > li` merged with `template_data`."""
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        worshipped_map = params.get("godsWorshipped")
        if not isinstance(worshipped_map, dict):
            worshipped_map = {}

        active_slot_gods = {
            slot.godId for slot in self.worshipSlots if slot.godId is not None
        }
        researched_set = set(self.researchedGodIds)

        gods: List[ShrineGodStatus] = []
        for li in soup.select("#tabOverview ul.gods.overview > li[data-god-id]"):
            god_id = parse_int(li.get("data-god-id"))
            if god_id is None:
                continue

            slug = ""
            for cls in li.get("class", []):
                if cls.startswith("god_") and cls != "god_small":
                    slug = cls[len("god_"):]
                    break
            if not slug:
                small_div = li.select_one("div.god_small")
                if small_div is not None:
                    for cls in small_div.get("class", []):
                        if cls.startswith("god_") and cls != "god_small":
                            slug = cls[len("god_"):]
                            break

            name_el = li.select_one(".godDescription > b")
            name = _clean_text(name_el.get_text(" ", strip=True)) if name_el else slug.title()

            req_res_div = li.select_one(".requirements.research")
            req_bld_div = li.select_one(".requirements.building")
            req_res_a = req_res_div.select_one("a") if req_res_div else None
            req_bld_a = req_bld_div.select_one("a") if req_bld_div else None

            is_researched = (
                god_id in researched_set
                if researched_set
                else (
                    req_res_div is None
                    or "invisible" in (req_res_div.get("class") or [])
                )
            )
            is_building_met = (
                req_bld_div is None or "invisible" in (req_bld_div.get("class") or [])
            )

            # Grace period, favour bar progress, and extension status come primarily from template_data.
            sel_base = f"shrineOfOlympus .god_{slug}"
            grace_raw = _tmpl_lookup(
                tmpl, f"{sel_base} .gracePeriod", f"#{sel_base} .gracePeriod"
            )
            if grace_raw is None:
                gp_el = li.select_one(".gracePeriod")
                grace_raw = gp_el.get_text(" ", strip=True) if gp_el else ""
            elif isinstance(grace_raw, dict):
                grace_raw = grace_raw.get("text", "")
            grace_str = _clean_text(grace_raw)
            if grace_str in ("", "-"):
                grace_str = ""
                grace_seconds = None
            else:
                grace_seconds = parse_duration_seconds(grace_str)

            prog_val = _tmpl_lookup(
                tmpl, f"{sel_base} .progressbar .text", f"#{sel_base} .progressbar .text"
            )
            if prog_val is None:
                txt_el = li.select_one(".progressbar .text")
                parsed_prog = parse_int(txt_el.get_text(" ", strip=True)) if txt_el else None
                favor_donated = parsed_prog if parsed_prog is not None else 0
            elif isinstance(prog_val, dict):
                favor_donated = parse_int(prog_val.get("text")) or 0
            else:
                favor_donated = parse_int(prog_val) or 0

            inner_display = li.select_one(".progressbar .innerDisplay")
            favor_max = 1000
            if inner_display is not None and "/" in inner_display.get_text():
                rhs = inner_display.get_text().rsplit("/", 1)[1]
                parsed_max = parse_int(rhs)
                if parsed_max is not None:
                    favor_max = parsed_max

            favor_percent: Optional[float] = None
            bar_val = _tmpl_lookup(tmpl, f"{sel_base} .bar", f"#{sel_base} .bar")
            if isinstance(bar_val, dict) and isinstance(bar_val.get("style"), dict):
                favor_percent = parse_float(bar_val["style"].get("width"))
            if favor_percent is None:
                bar_el = li.select_one(".progressbar .bar[style]")
                if bar_el is not None:
                    m_w = _STYLE_WIDTH_RE.search(str(bar_el.get("style", "")))
                    if m_w:
                        favor_percent = parse_float(m_w.group(1))
            if favor_percent is None and favor_max > 0 and favor_donated:
                favor_percent = round(favor_donated * 100.0 / favor_max, 2)

            god_card_cmd = _tmpl_lookup(tmpl, sel_base, f"#{sel_base}")
            can_extend = False
            if isinstance(god_card_cmd, dict):
                can_extend = god_card_cmd.get("addClass") == "buyExtensionAllowed"
            elif "buyExtensionAllowed" in (li.get("class") or []):
                can_extend = True

            if str(god_id) in worshipped_map:
                is_worshipped = bool(worshipped_map[str(god_id)])
            elif god_id in active_slot_gods:
                is_worshipped = True
            else:
                is_worshipped = bool(grace_str or favor_donated > 0)

            submit_btn = li.select_one("input.button[type='submit']")
            can_donate = (
                submit_btn is not None
                and not submit_btn.has_attr("disabled")
                and "disabled" not in (submit_btn.get("class") or [])
            )

            gods.append(
                ShrineGodStatus(
                    godId=god_id,
                    slug=slug,
                    name=name,
                    isWorshipped=is_worshipped,
                    isResearched=is_researched,
                    isBuildingLevelMet=is_building_met,
                    gracePeriodText=grace_str,
                    gracePeriodSeconds=grace_seconds,
                    favorDonated=favor_donated if favor_donated is not None else 0,
                    favorMax=favor_max,
                    favorPercent=favor_percent,
                    canDonate=can_donate,
                    canExtendGrace=can_extend,
                    researchRequirement=_clean_text(req_res_a.get_text(" ", strip=True))
                    if req_res_a
                    else "",
                    buildingRequirement=_clean_text(req_bld_a.get_text(" ", strip=True))
                    if req_bld_a
                    else "",
                )
            )

        self.gods = gods

    def _parse_worship_dom(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse `#tabWorship ul.gods.worshiping > li[data-number]` slots."""
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        slots: List[ShrineWorshipSlot] = []

        for li in soup.select("#tabWorship ul.gods.worshiping > li[data-number]"):
            slot_num = parse_int(li.get("data-number"))
            if slot_num is None:
                continue

            city_select = li.select_one("select.js_citySelect")
            god_select = li.select_one("select.js_godSelect")

            city_id: Optional[int] = None
            city_name: Optional[str] = None
            if city_select is not None:
                sel_city = city_select.find("option", selected=True)
                if sel_city is not None:
                    cid = parse_int(sel_city.get("value"))
                    if cid and cid > 0:
                        city_id = cid
                        city_name = _clean_text(sel_city.get_text(" ", strip=True))
                if city_id is None:
                    known_cid = parse_int(city_select.get("data-known-city-id"))
                    if known_cid and known_cid > 0:
                        city_id = known_cid

            god_id: Optional[int] = None
            god_name: Optional[str] = None
            if god_select is not None:
                sel_god = god_select.find("option", selected=True)
                if sel_god is not None:
                    gid = parse_int(sel_god.get("value"))
                    if gid and gid > 0:
                        god_id = gid
                        god_name = _clean_text(sel_god.get_text(" ", strip=True))

            slot_sel = f"shrineOfOlympus .gods.worshiping li[data-number={slot_num}]"

            start_raw = _tmpl_lookup(
                tmpl, f"{slot_sel} .startTime", f"#{slot_sel} .startTime"
            )
            if start_raw is None:
                el = li.select_one(".startTime")
                start_raw = el.get_text(" ", strip=True) if el else ""
            start_time = _clean_text(
                start_raw.get("text", "") if isinstance(start_raw, dict) else start_raw
            ) or None

            gen_raw = _tmpl_lookup(
                tmpl,
                f"{slot_sel} .generatedResources",
                f"#{slot_sel} .generatedResources",
            )
            if gen_raw is None:
                el = li.select_one(".generatedResources")
                gen_raw = el.get_text(" ", strip=True) if el else ""
            generated_res = parse_int(
                gen_raw.get("text") if isinstance(gen_raw, dict) else gen_raw
            )

            bonus_raw = _tmpl_lookup(
                tmpl, f"{slot_sel} .currentBonus", f"#{slot_sel} .currentBonus"
            )
            if bonus_raw is None:
                el = li.select_one(".currentBonus")
                bonus_raw = el.get_text(" ", strip=True) if el else ""
            current_bonus = parse_float(
                bonus_raw.get("text") if isinstance(bonus_raw, dict) else bonus_raw
            )

            slots.append(
                ShrineWorshipSlot(
                    slotNumber=slot_num,
                    cityId=city_id,
                    cityName=city_name,
                    godId=god_id,
                    godName=god_name,
                    startTime=start_time,
                    generatedResources=generated_res,
                    currentBonusPercent=current_bonus,
                )
            )

        self.worshipSlots = slots

    def parseOverview(self, viewData: Union[str, AjaxResponse]) -> "ShrineOfOlympus":
        """Parse ``activeTab=tabOverview`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabOverview"
        params = _parse_load_js_params(resp)
        self._parse_header_and_metadata(soup, resp, params)
        if not self.worshipSlots and soup.select_one("#tabWorship"):
            self._parse_worship_dom(soup, resp)
        self._parse_overview_dom(soup, resp, params)
        return self

    def parseWorship(self, viewData: Union[str, AjaxResponse]) -> "ShrineOfOlympus":
        """Parse ``activeTab=tabWorship`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabWorship"
        params = _parse_load_js_params(resp)
        self._parse_header_and_metadata(soup, resp, params)
        self._parse_worship_dom(soup, resp)
        return self

    async def loadOverview(self) -> "ShrineOfOlympus":
        """Fetch and parse ``activeTab=tabOverview``."""
        resp = await self._fetch_view(view="shrineOfOlympus", activeTab="tabOverview")
        return self.parseOverview(resp)

    async def loadWorship(self) -> "ShrineOfOlympus":
        """Fetch and parse ``activeTab=tabWorship``."""
        resp = await self._fetch_view(view="shrineOfOlympus", activeTab="tabWorship")
        return self.parseWorship(resp)

    async def loadAllTabs(self) -> "ShrineOfOlympus":
        """Refresh the Shrine of Olympus overview and worship tabs."""
        await self.load()
        await self.loadWorship()
        return self

    # --- Action Stubs (Read-only model: intentionally unimplemented) ---

    async def donateFavor(self, godId: int) -> "ShrineOfOlympus":
        """Donate Favour to improve or restore a god's grace."""
        if not self.isLoaded or not self.gods:
            await self.load()

        target_god = next((g for g in self.gods if g.godId == godId), None)
        if target_god is None:
            raise ValueError(f"Unknown godId {godId!r} for ShrineOfOlympus.")
        if not target_god.isResearched:
            raise ValueError(
                f"Cannot donate favor to {target_god.name}: research requirement "
                f"({target_god.researchRequirement}) is not met."
            )
        if not target_god.isBuildingLevelMet:
            raise ValueError(
                f"Cannot donate favor to {target_god.name}: building requirement "
                f"({target_god.buildingRequirement}) is not met."
            )
        if target_god.favorDonated >= target_god.favorMax:
            raise ValueError(
                f"Cannot donate favor to {target_god.name}: favor is already maxed "
                f"({target_god.favorDonated}/{target_god.favorMax})."
            )
        if self.currentFavor <= 0:
            raise ValueError(
                f"Not enough Favour to donate to {target_god.name} "
                f"(currentFavor={self.currentFavor})."
            )

        client = self._require_client()
        city_id = self.city.id if self.city is not None else self.cityId
        if city_id is None:
            raise ValueError("ShrineOfOlympus requires cityId to donate favor.")

        await client.post_action(
            payloadPost={
                "action": "DonateFavorToGod",
                "godId": str(godId),
                "backgroundView": "city",
                "currentCityId": str(city_id),
                "templateView": self.buildingType,
                "actionRequest": "REQUESTID",
                "ajax": "1",
            },
            metadata={"cityId": city_id, "godId": godId},
            action_name=f"ShrineOfOlympus.donateFavor({godId})",
        )
        await self.load()
        return self

    async def activateGod(self, godId: int, targetCityId: Optional[int] = None) -> Any:
        """Activate a god as a town's main deity (read-only stub)."""
        ...

    async def assignGodToCity(self, slotNumber: int, cityId: int, godId: int) -> Any:
        """Assign a deity to a worship slot for a city (read-only stub)."""
        ...

    async def extendGracePeriod(self, godId: int, itemId: int) -> Any:
        """Extend a deity's grace period using an Ambrosia fleece item (read-only stub)."""
        ...
