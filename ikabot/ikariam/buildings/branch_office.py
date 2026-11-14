"""Branch Office (Trading Post) building model (`view=branchOffice`, `buildingId=13`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import AjaxResponse, parse_float, parse_int, parse_query_int
from ikabot.ikariam.buildings._base import Building, parse_view_payload

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


_RESOURCE_ROWS: Tuple[Tuple[int, str, str], ...] = (
    (0, "resource", "wood"),
    (1, "tradegood1", "wine"),
    (2, "tradegood2", "marble"),
    (3, "tradegood3", "crystal"),
    (4, "tradegood4", "sulphur"),
)
_TRADE_TYPE_CODES: Dict[str, str] = {
    "buy": "444",
    "444": "444",
    "sell": "333",
    "333": "333",
}
_SEARCH_RESOURCE_CODES: Dict[str, str] = {
    "resource": "resource",
    "0": "resource",
    "wood": "resource",
    "1": "1",
    "wine": "1",
    "2": "2",
    "marble": "2",
    "3": "3",
    "crystal": "3",
    "glass": "3",
    "4": "4",
    "sulphur": "4",
    "sulfur": "4",
}
_OWN_OFFER_RESOURCE_NAMES: Dict[str, str] = {
    "0": "wood",
    "wood": "wood",
    "resource": "wood",
    "1": "wine",
    "wine": "wine",
    "tradegood1": "wine",
    "2": "marble",
    "marble": "marble",
    "tradegood2": "marble",
    "3": "crystal",
    "crystal": "crystal",
    "glass": "crystal",
    "tradegood3": "crystal",
    "4": "sulphur",
    "sulphur": "sulphur",
    "sulfur": "sulphur",
    "tradegood4": "sulphur",
}
# Note: in formkontor Own Offers dropdowns, 333 = "Buy" and 444 = "Sell"
# (opposite of the bargain search filter where "buy" searches others' 444 sell offers).
_OWN_OFFER_TYPE_CODES: Dict[str, str] = {
    "buy": "333",
    "333": "333",
    "sell": "444",
    "444": "444",
}
_LIMITS_RE = re.compile(r"(\d+)\s*-\s*(\d+)")
_INT_TOKEN_RE = re.compile(r"(\d[\d,.]*)")
_SCRIPT_RESOURCE_RE = re.compile(r"resources\[(\d)\]\s*=\s*(\d+)")
_SCRIPT_GOLD_RE = re.compile(r"\bvar\s+gold\s*=\s*([0-9.]+)")
_SCRIPT_STORAGE_RE = re.compile(r"\bvar\s+storageCapacity\s*=\s*(\d+)")
_WS_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    """Collapse internal whitespace cleanly."""
    return _WS_RE.sub(" ", str(value or "")).strip()


def _selected_option_value(select: Optional[Tag]) -> str:
    """Return the selected ``<option>`` value from a ``<select>`` tag."""
    if select is None:
        return ""
    opt = select.find("option", selected=True)
    if opt is None:
        opt = select.find("option")
    if opt is None:
        return ""
    return str(opt.get("value") if opt.has_attr("value") else _clean_text(opt.get_text()))


@dataclass
class BranchOfficeOffer:
    """Market offer row in Goods Trade, Soldier Exchange, or Trade Partners."""

    cityName: str = ""
    ownerName: str = ""
    cityId: Optional[int] = None
    goodsPerMinute: Optional[int] = None
    amount: Optional[int] = None
    itemName: str = ""
    price: Optional[int] = None
    distance: Optional[int] = None
    actionUrl: Optional[str] = None
    offerType: str = ""


@dataclass
class BranchOfficeOwnOffer:
    """Per-resource buy/sell offer configuration in ``Own Offers``."""

    resourceKey: str
    resourceName: str
    offerType: str = "sell"
    tradeTypeCode: int = 444
    amount: int = 0
    price: int = 0
    minPrice: Optional[int] = None
    maxPrice: Optional[int] = None
    cityStock: Optional[int] = None


class BranchOffice(Building):
    """Ikariam Trading Post / Branch Office model (``view=branchOffice``).

    Supports Goods Trade (``view=branchOffice``), Soldier Exchange
    (``view=branchOfficeSoldier``), Trade Partners
    (``view=branchOfficeTradePartners``), and Own Offers
    (``view=branchOfficeOwnOffers``).
    """

    buildingId: int = 13
    buildingType: str = "branchOffice"

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
        self.activeTab: str = "tab_branchOffice"
        self.storageCapacity: int = 0
        # Primary Goods Trade (#finder)
        self.searchTradeTypeCode: Optional[int] = None
        self.searchResource: str = "resource"
        self.searchRange: Optional[int] = None
        self.maxSearchRadius: Optional[int] = None
        self.offers: List[BranchOfficeOffer] = []
        # Soldier Exchange
        self.soldierSearchTypeCode: Optional[int] = None
        self.soldierResourceFilter: str = "all"
        self.soldierSearchRange: Optional[int] = None
        self.soldierMaxSearchRadius: Optional[int] = None
        self.soldierAvailableUnits: Dict[int, str] = {}
        self.soldierOffers: List[BranchOfficeOffer] = []
        # Trade Partners
        self.partnerFilterType: str = "resource"
        self.partnerResourceFilter: str = "all"
        self.partnerCurrencyFilter: str = "all"
        self.tradePartnerOffers: List[BranchOfficeOffer] = []
        # Own Offers
        self.ownOffers: Dict[str, BranchOfficeOwnOffer] = {}
        self.reservedGold: int = 0
        self.ownGold: Optional[float] = None

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse sidebar storage capacity and whichever Branch Office view is loaded."""
        self._parse_capacity(soup)

        if soup.select_one("#tab_branchOfficeOwnOffers") is not None or soup.select_one("form[name='formkontor']") is not None:
            self.activeTab = "tab_branchOfficeOwnOffers"
            self._parse_own_offers_dom(soup)
        elif soup.select_one("#tab_branchOfficeTradePartners") is not None:
            self.activeTab = "tab_branchOfficeTradePartners"
            self._parse_trade_partners_dom(soup)
        elif soup.select_one("#searchResult") is not None or soup.select_one("input[name='view'][value='branchOfficeSoldier']") is not None:
            self.activeTab = "tab_branchOfficeSoldier"
            self._parse_soldier_dom(soup)
        else:
            self.activeTab = "tab_branchOffice"
            self._parse_goods_trade_dom(soup)

    def _parse_capacity(self, soup: BeautifulSoup) -> None:
        """Parse storage capacity from `#branchOfficeCapacity`."""
        cap_box = soup.select_one("#branchOfficeCapacity p")
        if cap_box is not None:
            m_cap = _INT_TOKEN_RE.search(cap_box.get_text(" ", strip=True))
            cap = parse_int(m_cap.group(1)) if m_cap else None
            if cap is not None:
                self.storageCapacity = cap

    def _parse_offer_table(
        self,
        table: Optional[Tag],
        *,
        offer_type: str = "",
    ) -> List[BranchOfficeOffer]:
        """Parse any Branch Office offers table while skipping empty placeholders."""
        if table is None:
            return []

        offers: List[BranchOfficeOffer] = []
        for tr in table.select("tr"):
            if tr.find("th") is not None and tr.find("td") is None:
                continue
            if tr.select_one("td[colspan]") is not None:
                continue
            tds = tr.select("td")
            if len(tds) < 6:
                continue

            city_td = tds[0]
            city_text = _clean_text(city_td.get_text(" ", strip=True))
            city_link = city_td.select_one("a[href]")
            city_id = (
                parse_query_int(city_link.get("href"), "selectCity")
                or parse_query_int(city_link.get("href"), "cityId")
                if city_link
                else None
            )

            goods_per_min = parse_int(tds[1].get_text(" ", strip=True))
            amount = parse_int(tds[2].get_text(" ", strip=True))
            item_name = _clean_text(tds[3].get_text(" ", strip=True))
            if not item_name:
                img = tds[3].select_one("img[alt], img[title]")
                if img is not None:
                    item_name = _clean_text(img.get("title") or img.get("alt"))
            price = parse_int(tds[4].get_text(" ", strip=True))
            distance = parse_int(tds[5].get_text(" ", strip=True))

            action_url: Optional[str] = None
            if len(tds) > 6:
                action_a = tds[6].select_one("a[href]")
                action_url = action_a.get("href") if action_a else None
                if city_id is None and action_url:
                    city_id = parse_query_int(action_url, "targetCityId") or parse_query_int(
                        action_url, "cityId"
                    )

            offers.append(
                BranchOfficeOffer(
                    cityName=city_text,
                    cityId=city_id,
                    goodsPerMinute=goods_per_min,
                    amount=amount,
                    itemName=item_name,
                    price=price,
                    distance=distance,
                    actionUrl=action_url,
                    offerType=offer_type,
                )
            )
        return offers

    def _parse_range_select(self, container: Tag) -> Tuple[Optional[int], Optional[int]]:
        """Extract selected and maximum search radius from `#rangeSelect`."""
        select = container.select_one("#rangeSelect")
        if select is None:
            return None, None
        options = [parse_int(opt.get("value") or opt.get_text()) for opt in select.select("option")]
        nums = [val for val in options if val is not None]
        selected = parse_int(_selected_option_value(select))
        max_radius = max(nums) if nums else selected
        return selected, max_radius

    def _parse_goods_trade_dom(self, soup: BeautifulSoup) -> None:
        """Parse `#finder` Goods Trade controls and result table."""
        finder = soup.select_one("#finder") or soup
        checked_type = finder.select_one("input[name='type'][checked], input[name='type']:checked")
        self.searchTradeTypeCode = parse_int(checked_type.get("value")) if checked_type else None
        self.searchResource = _selected_option_value(finder.select_one("#searchResource")) or "resource"
        self.searchRange, self.maxSearchRadius = self._parse_range_select(finder)

        offer_type = "buy" if self.searchTradeTypeCode == 444 else ("sell" if self.searchTradeTypeCode == 333 else "")
        tables = finder.select("table.table01")
        result_table = None
        for tbl in tables:
            if "search" not in (tbl.get("class") or []):
                result_table = tbl
                break
        self.offers = self._parse_offer_table(result_table, offer_type=offer_type)

    def _parse_soldier_dom(self, soup: BeautifulSoup) -> None:
        """Parse Soldier Exchange (`view=branchOfficeSoldier`) filters and results."""
        main = soup.select_one("#mainview") or soup
        self.soldierSearchTypeCode = parse_int(_selected_option_value(main.select_one("#type")))
        res_select = main.select_one("#searchResource")
        self.soldierResourceFilter = _selected_option_value(res_select) or "all"

        units: Dict[int, str] = {}
        if res_select is not None:
            for opt in res_select.select("option"):
                uid = parse_int(opt.get("value"))
                if uid is not None:
                    units[uid] = _clean_text(opt.get_text(" ", strip=True))
        self.soldierAvailableUnits = units
        self.soldierSearchRange, self.soldierMaxSearchRadius = self._parse_range_select(main)
        self.soldierOffers = self._parse_offer_table(
            main.select_one("#searchResult"),
            offer_type="soldier",
        )

    def _parse_trade_partners_dom(self, soup: BeautifulSoup) -> None:
        """Parse Trade Partners (`view=branchOfficeTradePartners`) filters and offers."""
        tab = soup.select_one("#tab_branchOfficeTradePartners") or soup
        self.partnerFilterType = _selected_option_value(tab.select_one("#type")) or "resource"
        self.partnerResourceFilter = _selected_option_value(tab.select_one("#searchResource")) or "all"
        self.partnerCurrencyFilter = _selected_option_value(tab.select_one("#currency")) or "all"

        result_table = None
        for tbl in tab.select("table.table01"):
            if "search" not in (tbl.get("class") or []):
                result_table = tbl
                break
        self.tradePartnerOffers = self._parse_offer_table(result_table, offer_type="partner")

    def _parse_own_offers_dom(self, soup: BeautifulSoup) -> None:
        """Parse `form[name='formkontor']` Own Offers and inline JS stock metadata."""
        tab = soup.select_one("#tab_branchOfficeOwnOffers") or soup
        form = tab.select_one("form[name='formkontor']") or tab

        reserved_el = form.select_one("#reservedGold")
        reserved = parse_int(reserved_el.get_text(" ", strip=True)) if reserved_el else None
        self.reservedGold = reserved if reserved is not None else 0

        script_text = " ".join(s.get_text(" ") for s in tab.select("script"))
        stock_by_idx: Dict[int, int] = {}
        for m in _SCRIPT_RESOURCE_RE.finditer(script_text):
            stock_by_idx[int(m.group(1))] = int(m.group(2))

        m_gold = _SCRIPT_GOLD_RE.search(script_text)
        self.ownGold = parse_float(m_gold.group(1)) if m_gold else None
        m_cap = _SCRIPT_STORAGE_RE.search(script_text)
        if m_cap and self.storageCapacity == 0:
            self.storageCapacity = int(m_cap.group(1))

        offers: Dict[str, BranchOfficeOwnOffer] = {}
        for idx, res_key, res_name in _RESOURCE_ROWS:
            trade_select = form.select_one(f"#{res_key}TradeType")
            amount_input = form.select_one(f"#{res_key}")
            price_input = form.select_one(f"#{res_key}Price")
            if trade_select is None and amount_input is None:
                continue

            code = parse_int(_selected_option_value(trade_select)) or 444
            offer_type = "buy" if code == 333 else "sell"
            amount = parse_int(amount_input.get("value") if amount_input else None) or 0
            price = parse_int(price_input.get("value") if price_input else None) or 0

            min_price: Optional[int] = None
            max_price: Optional[int] = None
            row_tr = amount_input.find_parent("tr") if amount_input else None
            if row_tr is not None:
                last_td = row_tr.select("td")[-1] if row_tr.select("td") else None
                if last_td is not None:
                    m_lim = _LIMITS_RE.search(_clean_text(last_td.get_text(" ", strip=True)))
                    if m_lim:
                        min_price = int(m_lim.group(1))
                        max_price = int(m_lim.group(2))

            offers[res_name] = BranchOfficeOwnOffer(
                resourceKey=res_key,
                resourceName=res_name,
                offerType=offer_type,
                tradeTypeCode=code,
                amount=amount,
                price=price,
                minPrice=min_price,
                maxPrice=max_price,
                cityStock=stock_by_idx.get(idx),
            )

        self.ownOffers = offers

    def parseSoldier(self, viewData: Union[str, AjaxResponse]) -> "BranchOffice":
        """Parse ``view=branchOfficeSoldier`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tab_branchOfficeSoldier"
        self._parse_capacity(soup)
        self._parse_soldier_dom(soup)
        return self

    def parseTradePartners(self, viewData: Union[str, AjaxResponse]) -> "BranchOffice":
        """Parse ``view=branchOfficeTradePartners`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tab_branchOfficeTradePartners"
        self._parse_capacity(soup)
        self._parse_trade_partners_dom(soup)
        return self

    def parseOwnOffers(self, viewData: Union[str, AjaxResponse]) -> "BranchOffice":
        """Parse ``view=branchOfficeOwnOffers`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tab_branchOfficeOwnOffers"
        self._parse_capacity(soup)
        self._parse_own_offers_dom(soup)
        return self

    async def loadSoldier(self) -> "BranchOffice":
        """Fetch and parse ``view=branchOfficeSoldier``."""
        resp = await self._fetch_view(
            view="branchOfficeSoldier",
            activeTab="tab_branchOfficeSoldier",
        )
        return self.parseSoldier(resp)

    async def loadTradePartners(self) -> "BranchOffice":
        """Fetch and parse ``view=branchOfficeTradePartners``."""
        resp = await self._fetch_view(
            view="branchOfficeTradePartners",
            activeTab="tab_branchOfficeTradePartners",
        )
        return self.parseTradePartners(resp)

    async def loadOwnOffers(self) -> "BranchOffice":
        """Fetch and parse ``view=branchOfficeOwnOffers``."""
        resp = await self._fetch_view(
            view="branchOfficeOwnOffers",
            activeTab="tab_branchOfficeOwnOffers",
        )
        return self.parseOwnOffers(resp)

    async def loadAllTabs(self) -> "BranchOffice":
        """Refresh the primary Goods Trade view and all three secondary views."""
        await self.load()
        await self.loadSoldier()
        await self.loadTradePartners()
        await self.loadOwnOffers()
        return self

    # --- Action Stubs & Query Methods ---

    async def searchOffers(
        self,
        *,
        tradeType: Union[str, int] = "buy",
        resource: Union[str, int] = "resource",
        radius: Optional[int] = None,
    ) -> List[BranchOfficeOffer]:
        """Query Trading Post offers with filter criteria and update ``self.offers``."""
        client = self._require_client()
        if self.position is None:
            raise ValueError("BranchOffice position is required to search offers")

        type_key = str(tradeType).strip().lower()
        if type_key not in _TRADE_TYPE_CODES:
            raise ValueError(f"Unsupported tradeType {tradeType!r}; expected 'buy'/'444' or 'sell'/'333'")
        type_code = _TRADE_TYPE_CODES[type_key]

        res_key = str(resource).strip().lower()
        if res_key not in _SEARCH_RESOURCE_CODES:
            raise ValueError(f"Unsupported resource filter {resource!r}")
        res_code = _SEARCH_RESOURCE_CODES[res_key]

        search_radius = (
            radius
            if radius is not None
            else (self.searchRange if self.searchRange is not None else (self.maxSearchRadius or 1))
        )

        resp = await client.post_ajax(
            params={
                "cityId": str(self.cityId),
                "position": str(self.position),
                "view": "branchOffice",
                "activeTab": "bargain",
                "type": type_code,
                "searchResource": res_code,
                "range": str(search_radius),
                "backgroundView": "city",
                "currentCityId": str(self.cityId),
                "templateView": "branchOffice",
                "currentTab": "bargain",
                "actionRequest": "REQUESTID",
            }
        )
        self.parseView(resp)
        return self.offers

    async def buyResource(
        self,
        targetCityId: int,
        resource: str,
        amount: int,
        price: Optional[int] = None,
    ) -> Any:
        """Purchase resources from another player's offer (read-only stub)."""
        ...

    async def sellResource(
        self,
        targetCityId: int,
        resource: str,
        amount: int,
        price: Optional[int] = None,
    ) -> Any:
        """Sell resources to another player's buy order (read-only stub)."""
        ...

    async def buyUnits(
        self,
        targetCityId: int,
        unitId: int,
        amount: int,
    ) -> Any:
        """Buy troops or warships on Soldier Exchange (read-only stub)."""
        ...

    @staticmethod
    def _normalize_own_resource(resource: str) -> str:
        """Resolve a resource name or form field key to its ``ownOffers`` key."""
        key = str(resource).strip().lower()
        canonical = _OWN_OFFER_RESOURCE_NAMES.get(key)
        if canonical is None:
            raise ValueError(f"Unsupported offer resource {resource!r}")
        return canonical

    async def updateOffers(self, offers: Dict[str, BranchOfficeOwnOffer]) -> "BranchOffice":
        """Submit updated Own Offers table via ``formkontor`` preserving unspecified rows."""
        if self.position is None:
            raise ValueError("BranchOffice position is required to update offers")
        if not self.ownOffers:
            await self.loadOwnOffers()

        normalized = {
            self._normalize_own_resource(key): offer
            for key, offer in offers.items()
        }

        payload: Dict[str, str] = {}
        for _, res_key, res_name in _RESOURCE_ROWS:
            offer = normalized.get(res_name) or self.ownOffers.get(res_name)
            if offer is None:
                raise ValueError(f"Missing baseline Own Offers row for {res_name!r}")

            type_key = str(offer.offerType).strip().lower()
            type_code = _OWN_OFFER_TYPE_CODES.get(type_key)
            if type_code is None:
                type_code = _OWN_OFFER_TYPE_CODES.get(str(offer.tradeTypeCode))
            if type_code is None:
                raise ValueError(
                    f"Unsupported offerType {offer.offerType!r} / code {offer.tradeTypeCode!r}"
                )
            if offer.amount < 0:
                raise ValueError(f"Offer amount for {res_name} cannot be negative ({offer.amount})")
            if offer.price <= 0:
                raise ValueError(f"Offer price for {res_name} must be positive ({offer.price})")

            payload[f"{res_key}TradeType"] = type_code
            payload[res_key] = str(int(offer.amount))
            payload[f"{res_key}Price"] = str(int(offer.price))

        resp = await self._post_building_action(
            action="CityScreen",
            function="updateOffers",
            templateView="branchOfficeOwnOffers",
            extraParams={"activeTab": "tab_branchOfficeOwnOffers"},
            payloadPost=payload,
            action_name="BranchOffice.updateOffers",
            refresh=False,
        )
        if resp.view_html and "formkontor" in resp.view_html:
            self.parseOwnOffers(resp)
        else:
            await self.loadOwnOffers()
        return self

    async def postOffer(
        self,
        resource: str,
        offerType: str,
        amount: int,
        price: int,
    ) -> "BranchOffice":
        """Create or update a single buy/sell offer in Own Offers."""
        res_name = self._normalize_own_resource(resource)
        type_code = _OWN_OFFER_TYPE_CODES.get(str(offerType).strip().lower())
        if type_code is None:
            raise ValueError(f"Unsupported offerType {offerType!r}; expected 'buy'/'333' or 'sell'/'444'")
        if not self.ownOffers:
            await self.loadOwnOffers()
        existing = self.ownOffers[res_name]
        norm_type = "buy" if type_code == "333" else "sell"
        updated = replace(
            existing,
            offerType=norm_type,
            tradeTypeCode=int(type_code),
            amount=int(amount),
            price=int(price),
        )
        return await self.updateOffers({res_name: updated})

    async def cancelOffer(self, resource: str) -> "BranchOffice":
        """Zero out / cancel an existing offer for ``resource``."""
        res_name = self._normalize_own_resource(resource)
        if not self.ownOffers:
            await self.loadOwnOffers()
        existing = self.ownOffers[res_name]
        updated = replace(existing, amount=0)
        return await self.updateOffers({res_name: updated})
