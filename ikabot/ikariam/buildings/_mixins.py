"""Shared building family mixins to eliminate duplicated parsing logic."""

from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    make_soup,
    parse_float,
    parse_int,
    parse_query_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_labeled_coords,
    parse_resources_ul,
    tmpl_int,
    tmpl_text,
)
from ikabot.ikariam.data import Resources, Unit, Units


@dataclass
class CostReductionEntry:
    """Cost reduction breakdown for a single category (e.g. Building, Units, Ships)."""

    category: str
    basePercent: float
    researchReductionPercent: float
    buildingReductionPercent: float
    finalCostPercent: float


@dataclass
class ResourceStorageEntry:
    """Safe, lootable, total, and capacity values for a single resource in a city."""

    resource: str
    safe: int
    lootable: int
    total: int
    capacity: int


@dataclass
class StorageContributor:
    """Single storage building row in ``#warehouseList``."""

    name: str
    buildingType: Optional[str]
    level: Optional[int]
    position: Optional[int]
    safeCapacity: int
    totalCapacity: int


@dataclass
class RecruitmentUnitSlot:
    """Single unit or warship recruitment slot in Barracks or Shipyard."""

    slotIndex: int
    unitId: int
    unit: Optional[Unit]
    name: str
    cssClass: str
    available: int
    description: str
    cost: Resources
    upkeep: Optional[int]
    trainingTimeSeconds: Optional[int]
    offensiveUpgradeName: Optional[str]
    offensiveUpgradeLevel: Optional[int]
    defensiveUpgradeName: Optional[str]
    defensiveUpgradeLevel: Optional[int]
    canRecruit: bool
    maxRecruitable: int
    blockedReason: Optional[str]


@dataclass
class RecruitmentQueueEntry:
    """Active unit or warship construction batch in ``#unitConstructionList``."""

    queueId: int
    armyType: str
    remainingText: Optional[str] = None
    units: Dict[int, int] = field(default_factory=dict)
    unitNames: Dict[str, int] = field(default_factory=dict)


@dataclass
class EmpireCityEntry:
    """Row in the Palace / Governor's Residence ``Towns in Your Empire`` table."""

    name: str
    isCapital: bool
    townHallLevel: int
    palaceLevel: int
    islandName: str
    x: int
    y: int
    luxuryResource: Optional[str]


class _ProductionBonusBuilding(Building):
    """Shared base for Forester, Stonemason, Glassblowing, Winegrower, and Alchemist."""

    basicProduction: float
    premiumBonus: float
    premiumRemaining: Optional[str]
    cinetheatreBonus: float
    cinetheatreRemaining: Optional[str]
    heliosBonus: float
    heliosRemaining: Optional[str]
    godsBonus: float
    buildingBonus: float
    totalProduction: float
    adVideoCooldownSeconds: Optional[int]
    adVideoEndTime: Optional[datetime]

    def _init_bonus_defaults(self) -> None:
        self.basicProduction = 0.0
        self.premiumBonus = 0.0
        self.premiumRemaining = None
        self.cinetheatreBonus = 0.0
        self.cinetheatreRemaining = None
        self.heliosBonus = 0.0
        self.heliosRemaining = None
        self.godsBonus = 0.0
        self.buildingBonus = 0.0
        self.totalProduction = 0.0
        self.adVideoCooldownSeconds = None
        self.adVideoEndTime = None

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        self._init_bonus_defaults()
        tbl = soup.select_one("#bonusBuilding table.table01") or soup.select_one("table.table01")
        if tbl is not None:
            for tr in tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                label = tds[0].get_text(" ", strip=True).rstrip(":").strip()
                val = parse_float(tds[1].get_text(" ", strip=True))
                rem_raw = tds[2].get_text(" ", strip=True) if len(tds) >= 3 else ""
                rem = rem_raw if rem_raw and rem_raw != "-" else None

                lower = label.lower()
                if lower.startswith("basic production") and val is not None:
                    self.basicProduction = val
                elif lower.startswith("premium bonus") and val is not None:
                    self.premiumBonus = val
                    self.premiumRemaining = rem
                elif lower.startswith("cinetheatre") and val is not None:
                    self.cinetheatreBonus = val
                    self.cinetheatreRemaining = rem
                elif lower.startswith("helios") and val is not None:
                    self.heliosBonus = val
                    self.heliosRemaining = rem
                elif lower.startswith("gods") and val is not None:
                    self.godsBonus = val
                elif not label and val is not None:
                    self.totalProduction = val
                elif val is not None:
                    self.buildingBonus = val

        ad_cd = resp.template_data.get("adVideoCooldown")
        if isinstance(ad_cd, dict):
            cd = ad_cd.get("countdown")
            if isinstance(cd, dict):
                end_ts = parse_int(cd.get("enddate"))
                cur_ts = parse_int(cd.get("currentdate"))
                if end_ts is not None:
                    self.adVideoEndTime = datetime.fromtimestamp(end_ts)
                    if cur_ts is not None:
                        self.adVideoCooldownSeconds = max(0, end_ts - cur_ts)


class _CostReductionBuilding(Building):
    """Shared base for Carpentering, Architect, Optician, Vineyard, and Fireworker."""

    reductions: Dict[str, CostReductionEntry]

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        self.reductions = {}
        for box in soup.select(".contentBox01h"):
            h3 = box.find("h3")
            tbl = box.find("table", class_="table01")
            if h3 is None or tbl is None:
                continue
            header_text = h3.get_text(" ", strip=True)
            if "cost reduction" not in header_text.lower():
                continue
            category = header_text.rsplit(None, 1)[-1].lower()
            base_pct = 100.0
            research_pct = 0.0
            building_pct = 0.0
            final_pct = 100.0

            for tr in tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                label = tds[0].get_text(" ", strip=True)
                pct_val = parse_float(tds[1].get_text(" ", strip=True))
                if pct_val is None:
                    continue
                lower = label.lower()
                if "basic costs" in lower:
                    base_pct = pct_val
                elif "research" in lower:
                    m_pct = re.search(r"\(([\d.,]+)%\)", label)
                    if m_pct:
                        research_pct = parse_float(m_pct.group(1)) or 0.0
                    final_pct = pct_val
                else:
                    m_pct = re.search(r"\(([\d.,]+)%\)", label)
                    if m_pct:
                        building_pct = parse_float(m_pct.group(1)) or 0.0
                    final_pct = pct_val

            self.reductions[category] = CostReductionEntry(
                category=category,
                basePercent=base_pct,
                researchReductionPercent=research_pct,
                buildingReductionPercent=building_pct,
                finalCostPercent=final_pct,
            )


class _StorageBuilding(Building):
    """Shared base for Warehouse and Depot (``dump``)."""

    storageByResource: Dict[str, ResourceStorageEntry]
    safeResources: Resources
    lootableResources: Resources
    totalResources: Resources
    storageCapacity: Resources
    totalSafeCapacity: int
    totalStorageCapacity: int
    safeCapacityBonusActive: bool
    storageCapacityBonusActive: bool
    storageBuildings: List[StorageContributor]

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        key_map = (
            ("wood", "wood"),
            ("wine", "wine"),
            ("marble", "marble"),
            ("glass", "crystal"),
            ("sulfur", "sulphur"),
        )
        self.storageByResource = {}
        safe_kw: Dict[str, int] = {}
        loot_kw: Dict[str, int] = {}
        total_kw: Dict[str, int] = {}
        cap_kw: Dict[str, int] = {}

        for ika_key, py_key in key_map:
            safe = tmpl_int(resp, f"js_secure_{ika_key}", "tooltip") or tmpl_int(resp, f"js_secure_{ika_key}") or 0
            loot = tmpl_int(resp, f"js_plunderable_{ika_key}", "tooltip") or tmpl_int(resp, f"js_plunderable_{ika_key}") or 0
            tot = tmpl_int(resp, f"js_total_{ika_key}", "tooltip") or tmpl_int(resp, f"js_total_{ika_key}") or 0
            cap = tmpl_int(resp, f"js_capacity_{ika_key}", "tooltip") or tmpl_int(resp, f"js_capacity_{ika_key}") or 0
            safe_kw[py_key] = safe
            loot_kw[py_key] = loot
            total_kw[py_key] = tot
            cap_kw[py_key] = cap
            self.storageByResource[py_key] = ResourceStorageEntry(
                resource=py_key,
                safe=safe,
                lootable=loot,
                total=tot,
                capacity=cap,
            )

        self.safeResources = Resources(**safe_kw)
        self.lootableResources = Resources(**loot_kw)
        self.totalResources = Resources(**total_kw)
        self.storageCapacity = Resources(**cap_kw)
        self.totalSafeCapacity = (
            tmpl_int(resp, "js_total_safe_capacity", "tooltip")
            or tmpl_int(resp, "js_total_safe_capacity")
            or 0
        )
        self.totalStorageCapacity = (
            tmpl_int(resp, "js_total_storage_capacity", "tooltip")
            or tmpl_int(resp, "js_total_storage_capacity")
            or 0
        )
        self.safeCapacityBonusActive = (
            parse_int(resp.template_data.get("js_safe_capacity_bonus_total")) or 0
        ) > 0
        self.storageCapacityBonusActive = (
            parse_int(resp.template_data.get("js_storage_capacity_bonus_total")) or 0
        ) > 0

        self.storageBuildings = []
        wlist = soup.find(id="warehouseList")
        if wlist is not None:
            for tr in wlist.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 4:
                    continue
                img = tds[0].find("img")
                btype = str(img["title"]) if img and img.get("title") else None
                link = tds[1].find("a")
                raw_name = tds[1].get_text(" ", strip=True)
                clean_name = " ".join(raw_name.split())
                pos = parse_query_int(str(link["href"]), "position") if link and link.get("href") else None
                m_lvl = re.search(r"\(Level\s+(\d+)\)", clean_name, re.IGNORECASE)
                lvl = int(m_lvl.group(1)) if m_lvl else None

                safe_tip = tds[2].select_one(".tooltip")
                cap_tip = tds[3].select_one(".tooltip")
                safe_val = parse_int(safe_tip.get_text(strip=True)) if safe_tip else (parse_int(tds[2].get_text(strip=True)) or 0)
                cap_val = parse_int(cap_tip.get_text(strip=True)) if cap_tip else (parse_int(tds[3].get_text(strip=True)) or 0)

                self.storageBuildings.append(
                    StorageContributor(
                        name=clean_name,
                        buildingType=btype,
                        level=lvl,
                        position=pos,
                        safeCapacity=safe_val or 0,
                        totalCapacity=cap_val or 0,
                    )
                )


def _parse_upgrade_badge(title: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    """Split ``'Steel Spear (3)'`` into ``('Steel Spear', 3)``."""
    if not title or not title.strip():
        return None, None
    match = re.match(r"^(.*?)\s*\((\d+)\)\s*$", title.strip())
    if match:
        return match.group(1).strip(), int(match.group(2))
    return title.strip(), None


class _RecruitmentBuilding(Building):
    """Shared base for Barracks and Shipyard recruitment views."""

    units: List[RecruitmentUnitSlot]
    freeCitizens: int
    cityResources: Resources
    canRecruitNow: bool
    noBuildReason: Optional[str]
    constructionQueueSummary: Optional[str]
    constructionQueue: List[RecruitmentQueueEntry]

    def getUnit(self, unitOrId: Any) -> Optional[RecruitmentUnitSlot]:
        """Look up a recruitment slot by unit ID or :class:`Unit` instance."""
        target_id = unitOrId.id if isinstance(unitOrId, Unit) else parse_int(unitOrId)
        for slot in self.units:
            if slot.unitId == target_id:
                return slot
        return None

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        self.units = []
        self.freeCitizens = 0
        self.cityResources = Resources()
        self.canRecruitNow = True
        self.noBuildReason = None
        self.constructionQueueSummary = None

        load_js = resp.template_data.get("load_js")
        js_params: Dict[str, Any] = {}
        if isinstance(load_js, dict) and isinstance(load_js.get("params"), str):
            try:
                js_params = json.loads(load_js["params"], strict=False)
            except (ValueError, TypeError):
                js_params = {}

        if js_params:
            self.freeCitizens = parse_int(js_params.get("citizens")) or 0
            self.canRecruitNow = str(js_params.get("canBuild", "1")) == "1"
            reason = js_params.get("noBuildPossible")
            self.noBuildReason = str(reason) if reason else None
            city_res = js_params.get("cityResources")
            if isinstance(city_res, dict):
                self.cityResources = Resources(
                    wood=parse_int(city_res.get("wood")) or 0,
                    wine=parse_int(city_res.get("wine")) or 0,
                    marble=parse_int(city_res.get("marble")) or 0,
                    crystal=parse_int(city_res.get("crystal")) or 0,
                    sulphur=parse_int(city_res.get("sulfur")) or 0,
                    citizens=parse_int(city_res.get("citizens")) or 0,
                )

        queue_raw = resp.template_data.get("unitConstructionList.dynamic div:nth-of-type(1) h4")
        if isinstance(queue_raw, str) and queue_raw.strip():
            self.constructionQueueSummary = make_soup(queue_raw).get_text(" ", strip=True)

        self.constructionQueue = []
        for block in soup.select("#unitConstructionList .unitConstructionBlock"):
            abort_link = block.select_one("a[href*='createAbortPopup']")
            if abort_link is None or not abort_link.get("href"):
                continue
            m_abort = re.search(
                r"createAbortPopup\(\s*(\d+)\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
                str(abort_link["href"]),
            )
            if not m_abort:
                continue
            queue_id = int(m_abort.group(1))
            army_type = m_abort.group(2)
            cnt_el = block.select_one(f"#counter{queue_id}, .time")
            rem_text = cnt_el.get_text(" ", strip=True) if cnt_el else None
            queued_units: Dict[int, int] = {}
            queued_names: Dict[str, int] = {}
            for wrapper in block.select(".army_wrapper"):
                unit_title = str(wrapper.get("title") or "").strip()
                qty_el = wrapper.select_one(".unitcounttextlabel")
                qty = parse_int(qty_el.get_text(" ", strip=True)) if qty_el else None
                if not qty:
                    continue
                if unit_title:
                    queued_names[unit_title] = queued_names.get(unit_title, 0) + qty
                for child in wrapper.select(".army"):
                    for cls_name in child.get("class") or []:
                        m_uid = re.fullmatch(r"s(\d+)", str(cls_name))
                        if m_uid:
                            uid = int(m_uid.group(1))
                            queued_units[uid] = queued_units.get(uid, 0) + qty
                            break
            self.constructionQueue.append(
                RecruitmentQueueEntry(
                    queueId=queue_id,
                    armyType=army_type,
                    remainingText=rem_text,
                    units=queued_units,
                    unitNames=queued_names,
                )
            )

        buildable_map = js_params.get("buildable") if isinstance(js_params.get("buildable"), dict) else {}

        slot_idx = 1
        while f"js_barracksUnitClass{slot_idx}" in resp.template_data:
            css_class = str(
                (resp.template_data.get(f"js_barracksUnitClass{slot_idx}") or {}).get("class") or ""
            )
            name = tmpl_text(resp, f"js_barracksUnitName{slot_idx}")
            available = tmpl_int(resp, f"js_barracksUnitUnitsAvailable{slot_idx}") or 0
            desc = tmpl_text(resp, f"js_barracksUnitDescription{slot_idx}")
            help_entry = resp.template_data.get(f"js_barracksUnitHelp{slot_idx}")
            href = help_entry.get("href") if isinstance(help_entry, dict) else None

            unit_id = parse_query_int(href, "unitId") or parse_query_int(href, "shipId")
            if unit_id is None:
                inp = soup.find(id=f"js_barracksBuyTextfield{slot_idx}")
                unit_id = parse_int(inp.get("name")) if inp else None

            costs_html = tmpl_text(resp, f"js_barracksCosts{slot_idx}")
            costs_soup = make_soup(costs_html)
            cost_ul = costs_soup.select_one("ul.resources")
            unit_cost, _, train_secs, _ = parse_resources_ul(cost_ul)
            upkeep_li = cost_ul.select_one("li.upkeep") if cost_ul else None
            upkeep_val = None
            if upkeep_li is not None:
                hint = upkeep_li.select_one(".accesshint")
                if hint:
                    hint.decompose()
                upkeep_val = parse_int(upkeep_li.get_text(" ", strip=True))

            off_entry = resp.template_data.get(f"js_barracksOffUpgrade{slot_idx}")
            def_entry = resp.template_data.get(f"js_barracksDefUpgrade{slot_idx}")
            off_name, off_lvl = _parse_upgrade_badge(
                off_entry.get("title") if isinstance(off_entry, dict) else None
            )
            def_name, def_lvl = _parse_upgrade_badge(
                def_entry.get("title") if isinstance(def_entry, dict) else None
            )

            slider_entry = resp.template_data.get(f"js_barracksSlider{slot_idx}")
            slider_info = slider_entry.get("slider") if isinstance(slider_entry, dict) else {}
            max_rec = parse_int((slider_info or {}).get("max_value")) or 0

            prob_entry = resp.template_data.get(f"js_barracksProblemTextfield{slot_idx}")
            prob_txt = (
                str(prob_entry.get("text") or "").strip()
                if isinstance(prob_entry, dict)
                else ""
            )

            if unit_id is not None and str(unit_id) in buildable_map:
                can_rec = (parse_int(buildable_map.get(str(unit_id))) or 0) > 0 and not prob_txt
            else:
                can_rec = max_rec > 0 and not prob_txt

            unit_template = Units.getUnitById(unit_id) if unit_id is not None else None
            unit_obj = unit_template(available) if unit_template is not None else None

            if unit_id is not None:
                self.units.append(
                    RecruitmentUnitSlot(
                        slotIndex=slot_idx,
                        unitId=unit_id,
                        unit=unit_obj,
                        name=name,
                        cssClass=css_class,
                        available=available,
                        description=desc,
                        cost=unit_cost,
                        upkeep=upkeep_val,
                        trainingTimeSeconds=train_secs,
                        offensiveUpgradeName=off_name,
                        offensiveUpgradeLevel=off_lvl,
                        defensiveUpgradeName=def_name,
                        defensiveUpgradeLevel=def_lvl,
                        canRecruit=can_rec,
                        maxRecruitable=max_rec,
                        blockedReason=prob_txt or None,
                    )
                )
            slot_idx += 1

    @staticmethod
    def _normalize_recruit_units(units: Any) -> Dict[int, int]:
        """Normalize a dict, Unit, or sequence of Units/pairs into ``{unitId: count}``."""
        counts: Dict[int, int] = {}
        if isinstance(units, Unit):
            items = [(units.id, units.count)]
        elif isinstance(units, dict):
            items = [
                (k.id if isinstance(k, Unit) else int(k), int(v))
                for k, v in units.items()
            ]
        elif isinstance(units, (list, tuple)):
            items = []
            for entry in units:
                if isinstance(entry, Unit):
                    items.append((entry.id, entry.count))
                elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                    uid = entry[0].id if isinstance(entry[0], Unit) else int(entry[0])
                    items.append((uid, int(entry[1])))
                else:
                    raise TypeError(f"Unsupported unit entry {entry!r}")
        else:
            raise TypeError(f"Unsupported units specification {units!r}")

        for uid, cnt in items:
            if cnt < 0:
                raise ValueError(f"Recruitment count for unit {uid} cannot be negative ({cnt})")
            if cnt > 0:
                counts[int(uid)] = counts.get(int(uid), 0) + int(cnt)
        if not counts:
            raise ValueError("At least one unit with positive count must be specified")
        return counts

    async def recruit(self, units: Any) -> "_RecruitmentBuilding":
        """Recruit the specified units or warships in this building."""
        if self.position is None:
            raise ValueError(f"{type(self).__name__} position is required to recruit")
        counts = self._normalize_recruit_units(units)
        function = "buildUnits" if self.buildingType == "barracks" else "buildShips"
        payload_extra = {str(uid): str(cnt) for uid, cnt in counts.items()}
        await self._post_building_action(
            action="CityScreen",
            function=function,
            templateView=self.buildingType or "barracks",
            payloadPost=payload_extra,
            metadata={"ambrosia_cost": 0},
            action_name=f"{type(self).__name__}.recruit",
            refresh=True,
        )
        return self

    async def cancelRecruitment(self, queueId: int) -> "_RecruitmentBuilding":
        """Abort a queued unit or warship construction batch."""
        if self.position is None:
            raise ValueError(f"{type(self).__name__} position is required to cancel recruitment")
        if not getattr(self, "constructionQueue", None):
            await self.load()

        entry = next(
            (q for q in self.constructionQueue if q.queueId == int(queueId)),
            None,
        )
        army_type = (
            entry.armyType
            if entry is not None
            else ("army" if self.buildingType == "barracks" else "fleet")
        )
        await self._require_client().post_action(
            params={
                "action": "CityScreen",
                "function": "abortMilitaryConstruction",
                "cityId": str(self.cityId),
                "position": str(self.position),
                "eid": str(queueId),
                "type": army_type,
                "backgroundView": "city",
                "currentCityId": str(self.cityId),
                "templateView": self.buildingType or "barracks",
                "actionRequest": "REQUESTID",
            },
            metadata={"ambrosia_cost": 0},
            action_name=f"{type(self).__name__}.cancelRecruitment",
        )
        await self.load()
        return self


class _GovernanceBuilding(Building):
    """Shared empire towns table parser for Palace and Governor's Residence."""

    empireCities: List[EmpireCityEntry]
    maxEmpireCities: Optional[int]

    def _parse_empire_table(self, soup: BeautifulSoup) -> None:
        self.empireCities = []
        self.maxEmpireCities = None

        for box in soup.select(".contentBox01h"):
            h3 = box.find("h3")
            if h3 is None or "towns in your empire" not in h3.get_text(" ", strip=True).lower():
                continue
            m_cap = re.search(r"\(\s*\d+\s*/\s*(\d+)\s*\)", h3.get_text(" ", strip=True))
            if m_cap:
                self.maxEmpireCities = int(m_cap.group(1))
            tbl = box.select_one("table.table01")
            if tbl is None:
                continue
            for tr in tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue
                is_capital = tds[0].find("img") is not None
                city_name = tds[1].get_text(" ", strip=True)
                th_lvl = parse_int(tds[2].get_text(strip=True)) or 0
                pal_lvl = parse_int(tds[3].get_text(strip=True)) or 0
                island_name, x, y = parse_labeled_coords(tds[4].get_text(" ", strip=True))
                res_img = tds[5].find("img")
                lux = (
                    str(res_img.get("title") or res_img.get("alt") or "").strip()
                    if res_img is not None
                    else None
                )
                self.empireCities.append(
                    EmpireCityEntry(
                        name=city_name,
                        isCapital=is_capital,
                        townHallLevel=th_lvl,
                        palaceLevel=pal_lvl,
                        islandName=island_name,
                        x=x,
                        y=y,
                        luxuryResource=lux or None,
                    )
                )
