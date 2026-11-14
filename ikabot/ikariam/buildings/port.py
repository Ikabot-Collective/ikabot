"""Model for the Ikariam Trading Port building (``view=port``)."""

from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import (
    AjaxResponse,
    make_soup,
    parse_int,
    parse_query_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_labeled_coords,
    tmpl_int,
    tmpl_text,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


_LUXURY_CLASS_MAP = {
    "wood": "wood",
    "wine": "wine",
    "marble": "marble",
    "crystal": "crystal",
    "glass": "crystal",
    "sulfur": "sulphur",
    "sulphur": "sulphur",
}


def _extract_leading_int(text: Optional[str]) -> Optional[int]:
    """Extract the first formatted integer token from ``text``."""
    if not text:
        return None
    match = re.search(r"-?\d(?:[\d.,\xa0\u202f]*\d)?", text)
    return parse_int(match.group(0)) if match else None


def _parse_ship_tooltip_stats(tooltip_html: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract ``(speed, transportCapacity)`` from a port ship tooltip snippet."""
    if not tooltip_html:
        return None, None
    text = make_soup(tooltip_html).get_text("\n", strip=True)
    m_speed = re.search(r"Speed\s*:\s*([0-9.,\xa0\u202f]+)", text, re.IGNORECASE)
    m_cap = re.search(r"Transport capacity\s*:\s*([0-9.,\xa0\u202f]+)", text, re.IGNORECASE)
    return (
        parse_int(m_speed.group(1)) if m_speed else None,
        parse_int(m_cap.group(1)) if m_cap else None,
    )


def _selected_option(select_tag: Optional[Tag]) -> Optional[Tag]:
    """Return the selected ``<option>`` element from a ``<select>`` tag."""
    if select_tag is None:
        return None
    for opt in select_tag.find_all("option"):
        if opt.has_attr("selected"):
            return opt
    return None


@dataclass
class PortCityBox:
    """Target own city card shown in the Port's ``Send Merchant Ship`` tab."""

    cityId: int
    name: str
    x: int = 0
    y: int = 0
    level: int = 0
    luxuryResource: Optional[str] = None
    transportUrl: Optional[str] = None


@dataclass
class PortFleetEntry:
    """Fleet row listed under ``Fleets Being Loaded`` in the Port."""

    category: str
    cells: List[str] = field(default_factory=list)


@dataclass
class PortLoadingSpeedEntry:
    """Port loading speed contribution row in ``table.loading_speed_table``."""

    label: str
    level: Optional[int]
    goodsPerMinute: int


@dataclass
class PortTradeRoute:
    """Configured or editable trade route entry in the Port's ``Trade Route`` tab."""

    routeIndex: int
    updatePosition: int
    durationDays: Optional[int]
    durationText: str
    sourceCityId: Optional[int]
    sourceCityName: str
    sourceX: int
    sourceY: int
    destinationCityId: Optional[int]
    destinationCityName: str
    destinationX: int
    destinationY: int
    tradegoodId: Optional[int]
    tradegoodName: str
    amount: int
    hour: Optional[int]
    timeText: str
    statusText: str
    isActive: bool
    canActivate: bool
    canDelete: bool
    deleteUrl: Optional[str] = None


class Port(Building):
    """Trading Port model covering transport targets, loading speed, ships, and trade routes."""

    activeTab: str

    cityBoxes: List[PortCityBox]
    loadingFleets: List[PortFleetEntry]
    ownOutgoingFleets: List[PortFleetEntry]
    foreignOutgoingFleets: List[PortFleetEntry]
    incomingFleets: List[PortFleetEntry]
    raidFleets: List[PortFleetEntry]

    portLoadingSpeeds: List[PortLoadingSpeedEntry]
    governmentLoadingBonus: int
    wonderLoadingBonus: int
    totalLoadingSpeed: int

    transportersOwned: int
    maxTransporters: int
    grantedTransporters: int
    friendListBonusTransporters: int
    governmentBonusTransporters: int
    dailyActivityBonusTransporters: int
    phoenicianTransportersOwned: int
    nextTransporterCostGold: Optional[int]
    nextPhoenicianTransporterCostAmbrosia: Optional[int]
    canBuyTransporter: bool
    buyTransporterWarning: Optional[str]
    buyPhoenicianTransporterWarning: Optional[str]
    transporterSpeed: Optional[int]
    transporterCapacity: Optional[int]

    freightersOwned: int
    maxNormalFreighters: int
    phoenicianFreightersOwned: int
    maxPhoenicianFreighters: int
    totalFreighters: int
    maxTotalFreighters: int
    nextFreighterCostGold: Optional[int]
    nextPhoenicianFreighterCostAmbrosia: Optional[int]
    canBuyFreighter: bool
    buyFreighterWarning: Optional[str]
    buyPhoenicianFreighterWarning: Optional[str]
    freighterSpeed: Optional[int]
    freighterCapacity: Optional[int]

    tradeRoutes: List[PortTradeRoute]
    createTradeRouteUrl: Optional[str]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Trading Port model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "port"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Port payload."""
        self.activeTab = "tabSendTransporter"

        self.cityBoxes = []
        self.loadingFleets = []
        self.ownOutgoingFleets = []
        self.foreignOutgoingFleets = []
        self.incomingFleets = []
        self.raidFleets = []

        self.portLoadingSpeeds = []
        self.governmentLoadingBonus = 0
        self.wonderLoadingBonus = 0
        self.totalLoadingSpeed = 0

        self.transportersOwned = 0
        self.maxTransporters = 0
        self.grantedTransporters = 0
        self.friendListBonusTransporters = 0
        self.governmentBonusTransporters = 0
        self.dailyActivityBonusTransporters = 0
        self.phoenicianTransportersOwned = 0
        self.nextTransporterCostGold = None
        self.nextPhoenicianTransporterCostAmbrosia = None
        self.canBuyTransporter = False
        self.buyTransporterWarning = None
        self.buyPhoenicianTransporterWarning = None
        self.transporterSpeed = None
        self.transporterCapacity = None

        self.freightersOwned = 0
        self.maxNormalFreighters = 0
        self.phoenicianFreightersOwned = 0
        self.maxPhoenicianFreighters = 0
        self.totalFreighters = 0
        self.maxTotalFreighters = 0
        self.nextFreighterCostGold = None
        self.nextPhoenicianFreighterCostAmbrosia = None
        self.canBuyFreighter = False
        self.buyFreighterWarning = None
        self.buyPhoenicianFreighterWarning = None
        self.freighterSpeed = None
        self.freighterCapacity = None

        self.tradeRoutes = []
        self.createTradeRouteUrl = None

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract all Port tabs: transport targets, fleets, loading speed, ships, and routes."""
        self._reset_fields()

        for script in soup.find_all("script"):
            text = script.string or script.get_text() or ""
            m_tab = re.search(r"switchTab\(\s*['\"]([^'\"]+)['\"]\s*\)", text)
            if m_tab:
                self.activeTab = m_tab.group(1)
                break

        self._parse_city_boxes(soup, resp)
        self._parse_loading_fleets(soup)
        self._parse_loading_speed(soup, resp)
        self._parse_ship_purchase_tab(soup, resp)
        self._parse_trade_routes(soup)

    def _parse_city_boxes(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse destination town cards from ``#tabSendTransporter``."""
        city_ids: List[int] = []
        for li in soup.select("#tabSendTransporter ul.cities li.cityBox"):
            li_id = str(li.get("id") or "")
            m_id = re.fullmatch(r"js_cityBox(\d+)", li_id)
            if m_id:
                cid = int(m_id.group(1))
                if cid not in city_ids:
                    city_ids.append(cid)

        for key in resp.template_data:
            m_id = re.fullmatch(r"js_cityBoxName(\d+)", key)
            if m_id:
                cid = int(m_id.group(1))
                if cid not in city_ids:
                    city_ids.append(cid)

        for cid in city_ids:
            name = tmpl_text(resp, f"js_cityBoxName{cid}")
            if not name:
                name_el = soup.find(id=f"js_cityBoxName{cid}")
                name = name_el.get_text(" ", strip=True) if name_el is not None else ""

            coords_text = tmpl_text(resp, f"js_cityBoxCoords{cid}")
            if not coords_text:
                coords_el = soup.find(id=f"js_cityBoxCoords{cid}")
                coords_text = (
                    coords_el.get_text(" ", strip=True) if coords_el is not None else ""
                )
            _, x, y = parse_labeled_coords(coords_text)

            lvl_entry = resp.template_data.get(f"js_cityBoxLevel{cid}")
            if isinstance(lvl_entry, dict):
                lvl_classes = str(lvl_entry.get("class") or "").split()
            else:
                lvl_el = soup.find(id=f"js_cityBoxLevel{cid}")
                lvl_classes = list(lvl_el.get("class") or []) if lvl_el is not None else []
            level = 0
            for cls in lvl_classes:
                m_lvl = re.fullmatch(r"level(\d+)", cls)
                if m_lvl:
                    level = int(m_lvl.group(1))
                    break

            tg_entry = resp.template_data.get(f"js_cityBoxTradegood{cid}")
            tg_classes = (
                str(tg_entry.get("class") or "").split()
                if isinstance(tg_entry, dict)
                else []
            )
            if not tg_classes:
                tg_el = soup.find(id=f"js_cityBoxTradegood{cid}")
                if tg_el is not None:
                    tg_classes = list(tg_el.get("class") or [])
            luxury: Optional[str] = None
            for cls in tg_classes:
                if cls != "resource":
                    luxury = _LUXURY_CLASS_MAP.get(cls.lower(), cls.lower())
                    break

            link_entry = resp.template_data.get(f"js_cityBoxLink{cid}")
            transport_url: Optional[str] = None
            if isinstance(link_entry, dict) and link_entry.get("ajaxrequest"):
                transport_url = str(link_entry["ajaxrequest"])
            else:
                link_el = soup.find(id=f"js_cityBoxLink{cid}")
                if link_el is not None and link_el.get("href") not in (None, "", "#"):
                    transport_url = str(link_el["href"])

            self.cityBoxes.append(
                PortCityBox(
                    cityId=cid,
                    name=name,
                    x=x,
                    y=y,
                    level=level,
                    luxuryResource=luxury,
                    transportUrl=transport_url,
                )
            )

    def _parse_loading_fleets(self, soup: BeautifulSoup) -> None:
        """Parse active outgoing, incoming, and raid fleet tables if present."""
        category_map = {
            "your transport ships": "ownOutgoing",
            "foreign ships": "foreignOutgoing",
            "incoming traders": "incoming",
            "raids": "raid",
        }
        attr_map = {
            "ownOutgoing": self.ownOutgoingFleets,
            "foreignOutgoing": self.foreignOutgoingFleets,
            "incoming": self.incomingFleets,
            "raid": self.raidFleets,
        }

        for tcap in soup.select("#tabSendTransporter .tcap"):
            heading = tcap.get_text(" ", strip=True).lower()
            category = category_map.get(heading, heading)
            target_list = attr_map.get(category)

            for sib in tcap.find_next_siblings():
                if "tcap" in (sib.get("class") or []):
                    break
                if sib.name == "table":
                    for tr in sib.find_all("tr"):
                        tds = tr.find_all("td")
                        if not tds:
                            continue
                        entry = PortFleetEntry(
                            category=category,
                            cells=[td.get_text(" ", strip=True) for td in tds],
                        )
                        self.loadingFleets.append(entry)
                        if target_list is not None:
                            target_list.append(entry)

    def _parse_loading_speed(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse port loading speed breakdown and total goods/minute."""
        idx = 0
        while f"js_loadingSpeedPort{idx}" in resp.template_data:
            speed_text = tmpl_text(resp, f"js_loadingSpeedPort{idx}")
            img_entry = resp.template_data.get(f"js_loadingSpeedImgPort{idx}")
            label = (
                str(img_entry.get("title") or "").strip()
                if isinstance(img_entry, dict)
                else f"Port {idx}"
            )
            m_lvl = re.search(r"\(Level\s+(\d+)\)", label, re.IGNORECASE)
            lvl = int(m_lvl.group(1)) if m_lvl else None
            gpm = _extract_leading_int(speed_text) or 0
            self.portLoadingSpeeds.append(
                PortLoadingSpeedEntry(label=label, level=lvl, goodsPerMinute=gpm)
            )
            idx += 1

        if not self.portLoadingSpeeds:
            for tr in soup.select("table.loading_speed_table tr"):
                if tr.get("id") in ("js_governmentBonusRow", "js_wonderBonusRow"):
                    continue
                if tr.select_one("td.sum") is not None:
                    continue
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                speed_text = tds[1].get_text(" ", strip=True)
                if not speed_text:
                    continue
                img = tds[0].find("img")
                label = str(img.get("title") or "").strip() if img is not None else ""
                m_lvl = re.search(r"\(Level\s+(\d+)\)", label, re.IGNORECASE)
                lvl = int(m_lvl.group(1)) if m_lvl else None
                self.portLoadingSpeeds.append(
                    PortLoadingSpeedEntry(
                        label=label or "Port",
                        level=lvl,
                        goodsPerMinute=_extract_leading_int(speed_text) or 0,
                    )
                )

        gov_row = resp.template_data.get("js_governmentBonusRow")
        if not (isinstance(gov_row, dict) and gov_row.get("buttonState") == "hidden"):
            self.governmentLoadingBonus = (
                _extract_leading_int(tmpl_text(resp, "js_governmentBonusValue")) or 0
            )

        wonder_row = resp.template_data.get("js_wonderBonusRow")
        if not (isinstance(wonder_row, dict) and wonder_row.get("buttonState") == "hidden"):
            self.wonderLoadingBonus = (
                _extract_leading_int(tmpl_text(resp, "js_wonderBonusValue")) or 0
            )

        sum_text = tmpl_text(resp, "js_loadingSpeedSumValue")
        if not sum_text:
            sum_td = soup.select_one("table.loading_speed_table td.sum:not(:first-child)")
            sum_text = sum_td.get_text(" ", strip=True) if sum_td is not None else ""
        self.totalLoadingSpeed = _extract_leading_int(sum_text) or 0

    def _read_tab_int(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        key: str,
        html_id: Optional[str] = None,
    ) -> Optional[int]:
        """Read an integer from ``template_data[key]`` or HTML element ``#html_id``."""
        val = tmpl_int(resp, key)
        if val is not None:
            return val
        tag = soup.find(id=html_id or key)
        return parse_int(tag.get_text(" ", strip=True)) if tag is not None else None

    def _parse_ship_purchase_tab(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse merchant ship and freighter counts, bonuses, costs, and capacities."""
        self.transportersOwned = (
            self._read_tab_int(soup, resp, "js_currentBuyableTransporters")
            or self._read_tab_int(soup, resp, "bonusShipTableTransporters")
            or 0
        )
        self.maxTransporters = self._read_tab_int(soup, resp, "js_maxTransporter") or 0
        self.grantedTransporters = parse_int(resp.template_data.get("grantedTransporters")) or 0
        self.phoenicianTransportersOwned = (
            self._read_tab_int(soup, resp, "js_currentBuyablePhoenicianTransporters")
            or self._read_tab_int(soup, resp, "bonusShipTablePhoenicianTransporters")
            or 0
        )

        self.nextTransporterCostGold = self._read_tab_int(
            soup, resp, "js_transporterCosts"
        )
        self.nextPhoenicianTransporterCostAmbrosia = self._read_tab_int(
            soup, resp, "js_phoenicianTransporterCosts"
        )

        buy_tr_entry = resp.template_data.get("js_buyTransporterAction")
        if isinstance(buy_tr_entry, dict) and "buttonState" in buy_tr_entry:
            self.canBuyTransporter = (
                buy_tr_entry.get("buttonState") == "enabled"
                and self.nextTransporterCostGold is not None
            )
        else:
            buy_tr_a = soup.find(id="js_buyTransporterAction")
            self.canBuyTransporter = (
                buy_tr_a is not None
                and "disabled" not in (buy_tr_a.get("class") or [])
                and self.nextTransporterCostGold is not None
            )

        tr_warn = tmpl_text(resp, "js_buyTransporterWarning") or (
            soup.find(id="js_buyTransporterWarning").get_text(" ", strip=True)
            if soup.find(id="js_buyTransporterWarning") is not None
            else ""
        )
        self.buyTransporterWarning = tr_warn or None

        ph_tr_warn_el = soup.find(id="js_buyPhoenicianTransporterWarning")
        if ph_tr_warn_el is not None:
            self.buyPhoenicianTransporterWarning = (
                ph_tr_warn_el.get_text(" ", strip=True) or None
            )

        self.transporterSpeed, self.transporterCapacity = _parse_ship_tooltip_stats(
            tmpl_text(resp, "js_transporterTooltip")
        )

        # Bonus merchant ships table
        bonus_tbl = soup.select_one(".tradeShipColumn table.bonus_ship_table")
        if bonus_tbl is not None:
            for tr in bonus_tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                cls_list = tds[0].get("class") or []
                val = parse_int(tds[1].get_text(strip=True)) or 0
                if "grantedTransporters" in cls_list:
                    self.friendListBonusTransporters = val
                elif "governmentSymbol" in cls_list:
                    self.governmentBonusTransporters = val
                elif "dailyActivityBonusSymbol" in cls_list:
                    self.dailyActivityBonusTransporters = val

        # Freighters
        self.freightersOwned = (
            self._read_tab_int(soup, resp, "js_currentPurchasedFreighters")
            or self._read_tab_int(soup, resp, "bonusShipTableFreighters")
            or 0
        )
        max_fr = tmpl_int(resp, "js_currentBuyableFreighters")
        if max_fr is None:
            fr_scroll = soup.select_one(".freighterColumn .tradeShip.freightersShips .scroll_view")
            if fr_scroll is not None:
                m_fr = re.search(r"(\d+)\s*/\s*(\d+)", fr_scroll.get_text(" ", strip=True))
                if m_fr:
                    if not self.freightersOwned:
                        self.freightersOwned = int(m_fr.group(1))
                    max_fr = int(m_fr.group(2))
        self.maxNormalFreighters = max_fr or 0

        self.phoenicianFreightersOwned = (
            self._read_tab_int(soup, resp, "js_purchasedPhoenicianFreighters")
            or self._read_tab_int(soup, resp, "js_bonusShipTablePhoenicianFreighters")
            or 0
        )
        self.maxPhoenicianFreighters = (
            tmpl_int(resp, "js_currentBuyablePhoenicianFreighters") or 0
        )
        self.totalFreighters = self._read_tab_int(soup, resp, "js_freightersTotal") or 0
        self.maxTotalFreighters = tmpl_int(resp, "js_freightersMax") or 0

        self.nextFreighterCostGold = self._read_tab_int(soup, resp, "js_freighterCosts")
        self.nextPhoenicianFreighterCostAmbrosia = self._read_tab_int(
            soup, resp, "js_phoenicianFreighterCosts"
        )

        buy_fr_entry = resp.template_data.get("js_buyFreighterAction")
        if isinstance(buy_fr_entry, dict) and "buttonState" in buy_fr_entry:
            self.canBuyFreighter = (
                buy_fr_entry.get("buttonState") == "enabled"
                and self.nextFreighterCostGold is not None
            )
        else:
            buy_fr_a = soup.find(id="js_buyFreighterAction")
            self.canBuyFreighter = (
                buy_fr_a is not None
                and "hidden" not in (buy_fr_a.get("class") or [])
                and "disabled" not in (buy_fr_a.get("class") or [])
                and self.nextFreighterCostGold is not None
            )

        fr_warn = tmpl_text(resp, "js_buyFreighterWarning") or (
            soup.find(id="js_buyFreighterWarning").get_text(" ", strip=True)
            if soup.find(id="js_buyFreighterWarning") is not None
            else ""
        )
        self.buyFreighterWarning = fr_warn or None

        ph_fr_warn_el = soup.find(id="js_buyPhoenicianFreighterWarning")
        if ph_fr_warn_el is not None:
            self.buyPhoenicianFreighterWarning = (
                ph_fr_warn_el.get_text(" ", strip=True) or None
            )

        self.freighterSpeed, self.freighterCapacity = _parse_ship_tooltip_stats(
            tmpl_text(resp, "js_freighterTooltip")
        )

    def _parse_trade_routes(self, soup: BeautifulSoup) -> None:
        """Parse configured trade route forms from ``#tabTradeRoutes``."""
        new_link = soup.select_one("#tabTradeRoutes a[href*='newTradeRoute=1']")
        if new_link is not None and new_link.get("href"):
            self.createTradeRouteUrl = str(new_link["href"])

        for form in soup.select("#tabTradeRoutes form[id^='tradeRouteForm']"):
            form_id = str(form.get("id") or "")
            m_idx = re.fullmatch(r"tradeRouteForm(\d+)", form_id)
            route_idx = int(m_idx.group(1)) if m_idx else len(self.tradeRoutes)

            upd_input = form.find("input", attrs={"name": "updatePosition"})
            update_pos = (
                parse_int(upd_input.get("value")) if upd_input is not None else None
            ) or 0

            duration_text = ""
            duration_days: Optional[int] = None
            title_row = form.find_previous_sibling("div", class_="title_row")
            if title_row is not None:
                dur_el = title_row.select_one(".premium_duration")
                if dur_el is not None:
                    duration_text = " ".join(dur_el.get_text(" ", strip=True).split())
                    duration_days = _extract_leading_int(duration_text)

            src_opt = _selected_option(form.find("select", attrs={"name": "city1Id"}))
            src_id = parse_int(src_opt.get("value")) if src_opt is not None else None
            src_name, src_x, src_y = (
                parse_labeled_coords(src_opt.get_text(" ", strip=True))
                if src_opt is not None and src_id is not None
                else ("", 0, 0)
            )

            dst_opt = _selected_option(form.find("select", attrs={"name": "city2Id"}))
            dst_id = parse_int(dst_opt.get("value")) if dst_opt is not None else None
            dst_name, dst_x, dst_y = (
                parse_labeled_coords(dst_opt.get_text(" ", strip=True))
                if dst_opt is not None and dst_id is not None
                else ("", 0, 0)
            )

            status_el = form.select_one(".status")
            status_text = status_el.get_text(" ", strip=True) if status_el is not None else ""
            is_active = bool(status_text) and "not active" not in status_text.lower()

            num_input = form.find("input", attrs={"name": "number"})
            amount = (
                parse_int(num_input.get("value")) if num_input is not None else 0
            ) or 0

            tg_opt = _selected_option(form.find("select", attrs={"name": "tradegood"}))
            tg_id = parse_int(tg_opt.get("value")) if tg_opt is not None else None
            tg_name = (
                str(tg_opt.get("title") or tg_opt.get_text(" ", strip=True)).strip()
                if tg_opt is not None
                else ""
            )

            time_opt = _selected_option(form.find("select", attrs={"name": "time"}))
            hour = parse_int(time_opt.get("value")) if time_opt is not None else None
            time_text = time_opt.get_text(" ", strip=True) if time_opt is not None else ""

            renew_btn = form.select_one(".renew a")
            delete_btn = form.select_one(".delete a")
            delete_url: Optional[str] = None
            if delete_btn is not None:
                if delete_btn.get("href") and delete_btn.get("href") != "#":
                    delete_url = str(delete_btn["href"])
                elif delete_btn.get("onclick"):
                    m_del = re.search(
                        r"confirmTradeRouteDelete\(['\"]([^'\"]+)['\"]\)",
                        str(delete_btn["onclick"]),
                    )
                    if m_del:
                        delete_url = m_del.group(1)

            self.tradeRoutes.append(
                PortTradeRoute(
                    routeIndex=route_idx,
                    updatePosition=update_pos,
                    durationDays=duration_days,
                    durationText=duration_text,
                    sourceCityId=src_id,
                    sourceCityName=src_name,
                    sourceX=src_x,
                    sourceY=src_y,
                    destinationCityId=dst_id,
                    destinationCityName=dst_name,
                    destinationX=dst_x,
                    destinationY=dst_y,
                    tradegoodId=tg_id,
                    tradegoodName=tg_name,
                    amount=amount,
                    hour=hour,
                    timeText=time_text,
                    statusText=status_text,
                    isActive=is_active,
                    canActivate=renew_btn is not None,
                    canDelete=delete_btn is not None,
                    deleteUrl=delete_url,
                )
            )

    async def loadTab(self, activeTab: str) -> "Port":
        """Fetch and parse a specific Port tab (read-only view fetch)."""
        resp = await self._fetch_view(activeTab=activeTab)
        self.parseView(resp)
        return self

    async def loadAllTabs(self) -> "Port":
        """Load the Port view (all three tabs are returned inline in one payload)."""
        return await self.load()

    async def buyTransporter(self) -> Any:
        """Purchase one regular Merchant Ship with gold."""
        ...

    async def buyPhoenicianTransporter(self) -> Any:
        """Purchase one Phoenician Merchant Ship with Ambrosia."""
        ...

    async def buyFreighter(self) -> Any:
        """Purchase one regular Freighter with gold."""
        ...

    async def buyPhoenicianFreighter(self) -> Any:
        """Purchase one Phoenician Freighter with Ambrosia."""
        ...

    async def createTradeRoute(self) -> Any:
        """Create a new trade route slot."""
        ...

    async def editTradeRoute(
        self,
        routeIndex: int,
        sourceCityId: int,
        destinationCityId: int,
        tradegood: int,
        amount: int,
        hour: int,
        activate: bool = False,
    ) -> "Port":
        """Update a configured trade route without activating/spending Ambrosia."""
        if activate:
            from ikabot.ikariam.client import AmbrosiaBlockedError

            raise AmbrosiaBlockedError(
                "Port.editTradeRoute(activate=True) spends Ambrosia and is blocked"
            )
        if self.position is None:
            raise ValueError("Port position is required to edit trade routes")
        if amount < 0:
            raise ValueError(f"Trade route amount cannot be negative ({amount})")
        if not 0 <= int(hour) <= 23:
            raise ValueError(f"Trade route hour must be between 0 and 23 (got {hour})")
        if not self.tradeRoutes:
            await self.load()

        route = next((r for r in self.tradeRoutes if r.routeIndex == routeIndex), None)
        update_pos = (
            route.updatePosition
            if route is not None and route.updatePosition
            else (int(routeIndex) + 1)
        )
        await self._post_building_action(
            action="Premium",
            function="editTradeRoute",
            templateView="port",
            extraParams={"activeTab": "tabTradeRoutes"},
            payloadPost={
                "updatePosition": str(update_pos),
                "renew": "0",
                "oldView": "port",
                "activeTab": "tabTradeRoutes",
                "page": "0",
                "city1Id": str(sourceCityId),
                "city2Id": str(destinationCityId),
                "number": str(amount),
                "tradegood": str(tradegood),
                "time": str(hour),
            },
            metadata={"ambrosia_cost": 0},
            action_name="Port.editTradeRoute",
            refresh=True,
        )
        return self

    async def deleteTradeRoute(self, routeIndex: int) -> Any:
        """Delete an existing trade route."""
        ...
