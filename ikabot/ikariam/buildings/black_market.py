"""Black Market building model (`view=blackMarket`, `buildingId=31`)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import AjaxResponse, make_soup, parse_int, parse_query_int
from ikabot.ikariam.buildings._base import Building, parse_view_payload
from ikabot.ikariam.data import Resource, Unit, Units

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


_OFFER_RATIO_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
_TAX_PERCENT_RE = re.compile(r"(?:tax\s*(?:break|rate)[^0-9]*?)(\d+)\s*%", re.IGNORECASE)
_TAX_DELTA_RE = re.compile(r"Taxes?\s*:?\s*(-?\d+)\s*%", re.IGNORECASE)
_SWITCH_TAB_RE = re.compile(r'switchTab\(["\']([^"\']+)["\']\)')
_WS_RE = re.compile(r"\s+")


_BLACK_MARKET_CURRENCIES = {
    "0": "0",
    "wood": "0",
    "building material": "0",
    "1": "1",
    "wine": "1",
    "2": "2",
    "marble": "2",
    "3": "3",
    "crystal": "3",
    "glass": "3",
    "crystal glass": "3",
    "4": "4",
    "sulphur": "4",
    "sulfur": "4",
    "5": "5",
    "gold": "5",
}


def _resolve_currency_code(currency: Union[int, str, Resource]) -> str:
    """Resolve a currency specifier (ID, name, or ``Resource``) into ``'0'..'5'``."""
    if isinstance(currency, Resource):
        if 0 <= currency.id <= 5:
            return str(currency.id)
        raise ValueError(f"Unsupported Black Market Resource currency: {currency.name!r}")
    key = str(currency).strip().lower()
    if key in _BLACK_MARKET_CURRENCIES:
        return _BLACK_MARKET_CURRENCIES[key]
    raise ValueError(
        f"Unsupported Black Market currency {currency!r}; expected 0..5 or resource/gold name"
    )


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


@dataclass
class BlackMarketUnitOption:
    """Unit type available (or unlockable) for sale on the Black Market."""

    unitId: int
    name: str
    unit: Optional[Unit] = None
    availableAmount: int = 0
    canOffer: bool = False
    activeOfferCount: int = 0
    minPriceResource: Optional[int] = None
    maxPriceResource: Optional[int] = None
    minPriceGold: Optional[int] = None
    maxPriceGold: Optional[int] = None


@dataclass
class BlackMarketOwnOffer:
    """Active unit sale listing in ``#tabMyOffers``."""

    offerId: Optional[int] = None
    unitId: Optional[int] = None
    unitName: str = ""
    amount: int = 0
    currency: str = ""
    pricePerUnit: int = 0
    cancelUrl: Optional[str] = None


class BlackMarket(Building):
    """Ikariam Black Market model (``view=blackMarket``).

    Black Market tabs (``#tabOfferUnits`` and ``#tabMyOffers``) are switched
    client-side via ``switchTab(...)`` inside a single ``view=blackMarket``
    response. Players sell military units here (buyers browse them via Branch
    Office Soldier Exchange).
    """

    buildingId: int = 31
    buildingType: str = "blackMarket"

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
        self.activeTab: str = "tabOfferUnits"
        self.currentTaxPercent: Optional[int] = None
        self.nextLevelTaxDeltaPercent: Optional[int] = None
        self.openOffersCount: int = 0
        self.maxOffers: int = 0
        self.isMarketBlocked: bool = False
        self.marketStatusClass: str = ""
        self.infoText: str = ""
        self.cooldownActive: bool = False
        self.cooldownTimestamp: Optional[int] = None
        self.selectedUnitFreeAmount: int = 0
        self.defaultUnitAmount: int = 0
        self.defaultUnitPrice: int = 0
        self.minLimit: Optional[int] = None
        self.maxLimit: Optional[int] = None
        self.unitOptions: List[BlackMarketUnitOption] = []
        self.myOffers: List[BlackMarketOwnOffer] = []
        self.buyOffers: List[Any] = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse Black Market taxes, offerable units, and own listings."""
        params = _parse_load_js_params(resp)
        for script in soup.select("#mainview script"):
            m = _SWITCH_TAB_RE.search(script.get_text(" "))
            if m:
                self.activeTab = m.group(1)
                break

        self._parse_metadata(soup, resp, params)
        self._parse_offer_units_dom(soup, resp, params)
        self._parse_my_offers_dom(soup, resp)
        if soup.select_one("#tabBuyUnits") is not None:
            self._parse_buy_units_dom(soup)

    def _parse_metadata(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        params: Dict[str, Any],
    ) -> None:
        """Parse sidebar tax reduction, active tax rate, limits, and cooldown."""
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}

        info_sidebar = soup.select_one("#informationSidebar")
        if info_sidebar is not None:
            m_delta = _TAX_DELTA_RE.search(_clean_text(info_sidebar.get_text(" ", strip=True)))
            self.nextLevelTaxDeltaPercent = int(m_delta.group(1)) if m_delta else None
        elif isinstance(tmpl.get("nextLevel"), str):
            m_delta = _TAX_DELTA_RE.search(
                _clean_text(make_soup(tmpl["nextLevel"]).get_text(" ", strip=True))
            )
            self.nextLevelTaxDeltaPercent = int(m_delta.group(1)) if m_delta else None

        self.currentTaxPercent = parse_int(tmpl.get("currentTax"))

        info_box_cmd = tmpl.get("blackmarketInfoBox")
        if isinstance(info_box_cmd, dict):
            raw_html = info_box_cmd.get("text", "")
            self.marketStatusClass = _clean_text(info_box_cmd.get("class"))
            if raw_html:
                self.infoText = _clean_text(make_soup(str(raw_html)).get_text(" ", strip=True))
        else:
            info_div = soup.select_one("#blackmarketInfoBox")
            if info_div is not None:
                self.marketStatusClass = " ".join(info_div.get("class") or []).strip()
                self.infoText = _clean_text(info_div.get_text(" ", strip=True))

        if self.currentTaxPercent is None and self.infoText:
            m_tax = _TAX_PERCENT_RE.search(self.infoText)
            if m_tax:
                self.currentTaxPercent = int(m_tax.group(1))

        self.openOffersCount = parse_int(tmpl.get("openOffers")) or 0
        self.maxOffers = parse_int(tmpl.get("maxOffers")) or 0
        if self.maxOffers == 0:
            hdr = soup.select_one("#tabOfferUnits h3.header, #tabMyOffers h3.header")
            if hdr is not None:
                m_ratio = _OFFER_RATIO_RE.search(hdr.get_text(" ", strip=True))
                if m_ratio:
                    self.openOffersCount = int(m_ratio.group(1))
                    self.maxOffers = int(m_ratio.group(2))

        self.cooldownActive = bool(
            params.get("cooldownActive", tmpl.get("cooldownActive", False))
        )
        self.cooldownTimestamp = parse_int(params.get("cooldownTimeStamp"))
        self.isMarketBlocked = bool(params.get("isMarketBlocked", 0))

        self.minLimit = parse_int(tmpl.get("minLimit"))
        self.maxLimit = parse_int(tmpl.get("maxLimit"))
        if self.minLimit is None:
            min_el = soup.select_one("#minLimit")
            self.minLimit = parse_int(min_el.get_text(" ", strip=True)) if min_el else None
        if self.maxLimit is None:
            max_el = soup.select_one("#maxLimit")
            self.maxLimit = parse_int(max_el.get_text(" ", strip=True)) if max_el else None

    def _parse_offer_units_dom(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        params: Dict[str, Any],
    ) -> None:
        """Parse `#tabOfferUnits` selectable units and price bounds."""
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}

        free_el = soup.select_one("#js_offerUnitFreeAmount")
        self.selectedUnitFreeAmount = (
            parse_int(free_el.get_text(" ", strip=True)) or 0 if free_el else 0
        )

        amt_cmd = tmpl.get("js_unitAmount")
        if isinstance(amt_cmd, dict) and "value" in amt_cmd:
            self.defaultUnitAmount = parse_int(amt_cmd.get("value")) or 0
        else:
            amt_el = soup.select_one("#js_unitAmount")
            self.defaultUnitAmount = parse_int(amt_el.get("value") if amt_el else None) or 0

        price_cmd = tmpl.get("js_unitPrice")
        if isinstance(price_cmd, dict) and "value" in price_cmd:
            self.defaultUnitPrice = parse_int(price_cmd.get("value")) or 0
        else:
            price_el = soup.select_one("#js_unitPrice")
            self.defaultUnitPrice = parse_int(price_el.get("value") if price_el else None) or 0

        unit_counts = params.get("units") if isinstance(params.get("units"), dict) else {}
        min_prices = params.get("minPrice") if isinstance(params.get("minPrice"), dict) else {}
        max_prices = params.get("maxPrice") if isinstance(params.get("maxPrice"), dict) else {}
        min_res = min_prices.get("res") if isinstance(min_prices.get("res"), dict) else {}
        min_gold = min_prices.get("gold") if isinstance(min_prices.get("gold"), dict) else {}
        max_res = max_prices.get("res") if isinstance(max_prices.get("res"), dict) else {}
        max_gold = max_prices.get("gold") if isinstance(max_prices.get("gold"), dict) else {}
        max_offer_counts = (
            params.get("maxOffersUnits")
            if isinstance(params.get("maxOffersUnits"), dict)
            else {}
        )

        # template_data['js_offerAbleUnits'] injects <option> tags on AJAX loads.
        options_html = tmpl.get("js_offerAbleUnits")
        option_tags: List[Tag] = []
        if isinstance(options_html, str) and options_html.strip():
            option_tags = list(make_soup(options_html).select("option"))
        else:
            select_el = soup.select_one("#js_offerAbleUnits")
            if select_el is not None:
                option_tags = list(select_el.select("option"))

        units: List[BlackMarketUnitOption] = []
        seen_ids: set[int] = set()
        for opt in option_tags:
            uid = parse_int(opt.get("value"))
            if uid is None:
                continue
            seen_ids.add(uid)
            uid_key = str(uid)
            name = _clean_text(opt.get_text(" ", strip=True))
            avail = parse_int(unit_counts.get(uid_key)) or 0
            can_offer = (not opt.has_attr("disabled")) and avail >= 0
            if opt.has_attr("disabled") and avail == 0:
                can_offer = False

            units.append(
                BlackMarketUnitOption(
                    unitId=uid,
                    name=name,
                    unit=Units.getUnitById(uid),
                    availableAmount=avail,
                    canOffer=can_offer,
                    activeOfferCount=parse_int(max_offer_counts.get(uid_key)) or 0,
                    minPriceResource=parse_int(min_res.get(uid_key)),
                    maxPriceResource=parse_int(max_res.get(uid_key)),
                    minPriceGold=parse_int(min_gold.get(uid_key)),
                    maxPriceGold=parse_int(max_gold.get(uid_key)),
                )
            )

        if not units and unit_counts:
            for raw_uid, raw_cnt in unit_counts.items():
                uid = parse_int(raw_uid)
                if uid is None or uid in seen_ids:
                    continue
                uid_key = str(uid)
                unit_obj = Units.getUnitById(uid)
                avail = parse_int(raw_cnt) or 0
                units.append(
                    BlackMarketUnitOption(
                        unitId=uid,
                        name=unit_obj.name if unit_obj else f"Unit {uid}",
                        unit=unit_obj,
                        availableAmount=avail,
                        canOffer=avail > 0,
                        activeOfferCount=parse_int(max_offer_counts.get(uid_key)) or 0,
                        minPriceResource=parse_int(min_res.get(uid_key)),
                        maxPriceResource=parse_int(max_res.get(uid_key)),
                        minPriceGold=parse_int(min_gold.get(uid_key)),
                        maxPriceGold=parse_int(max_gold.get(uid_key)),
                    )
                )

        self.unitOptions = units

    def _parse_my_offers_dom(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse `#tabMyOffers` and/or `template_data['ownOffers']` listings."""
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        offers: List[BlackMarketOwnOffer] = []

        raw_own = tmpl.get("ownOffers")
        if isinstance(raw_own, list) and raw_own:
            for item in raw_own:
                if not isinstance(item, dict):
                    continue
                uid = parse_int(item.get("unitId") or item.get("unit_id"))
                unit_obj = Units.getUnitById(uid) if uid is not None else None
                cancel_url = str(item.get("actionLink") or "") or None
                offers.append(
                    BlackMarketOwnOffer(
                        offerId=parse_int(item.get("id") or item.get("offerId"))
                        or (parse_query_int(cancel_url, "offerId") if cancel_url else None),
                        unitId=uid,
                        unitName=_clean_text(
                            item.get("unitName") or (unit_obj.name if unit_obj else "")
                        ),
                        amount=parse_int(item.get("amount")) or 0,
                        currency=_clean_text(
                            item.get("currency") or item.get("resource") or item.get("resName")
                        ),
                        pricePerUnit=parse_int(item.get("price")) or 0,
                        cancelUrl=cancel_url,
                    )
                )

        if not offers:
            tab = soup.select_one("#tabMyOffers")
            if tab is not None and tab.select_one("#blackmarketNoOffers") is None:
                for tr in tab.select("table tr"):
                    if tr.find("th") is not None and tr.find("td") is None:
                        continue
                    if tr.select_one("td[colspan]") is not None:
                        continue
                    tds = tr.select("td")
                    if len(tds) < 4:
                        continue
                    cancel_link = tr.select_one("a[href]")
                    cancel_url = cancel_link.get("href") if cancel_link else None
                    offer_id = parse_query_int(cancel_url, "offerId") or parse_query_int(
                        cancel_url, "id"
                    )
                    offers.append(
                        BlackMarketOwnOffer(
                            offerId=offer_id,
                            unitName=_clean_text(tds[0].get_text(" ", strip=True)),
                            amount=parse_int(tds[1].get_text(" ", strip=True)) or 0,
                            currency=_clean_text(tds[2].get_text(" ", strip=True)),
                            pricePerUnit=parse_int(tds[3].get_text(" ", strip=True)) or 0,
                            cancelUrl=cancel_url,
                        )
                    )

        self.myOffers = offers

    def _parse_buy_units_dom(self, soup: BeautifulSoup) -> None:
        """Parse `#tabBuyUnits` if present in a custom/extended payload."""
        tab = soup.select_one("#tabBuyUnits")
        if tab is None:
            self.buyOffers = []
            return
        rows: List[Dict[str, Any]] = []
        for tr in tab.select("table tr"):
            if tr.find("th") is not None and tr.find("td") is None:
                continue
            if tr.select_one("td[colspan]") is not None:
                continue
            tds = tr.select("td")
            if tds:
                rows.append({"cells": [_clean_text(td.get_text(" ", strip=True)) for td in tds]})
        self.buyOffers = rows

    def parseOfferUnits(self, viewData: Union[str, AjaxResponse]) -> "BlackMarket":
        """Parse the inline ``tabOfferUnits`` section offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabOfferUnits"
        params = _parse_load_js_params(resp)
        self._parse_metadata(soup, resp, params)
        self._parse_offer_units_dom(soup, resp, params)
        return self

    def parseMyOffers(self, viewData: Union[str, AjaxResponse]) -> "BlackMarket":
        """Parse the inline ``tabMyOffers`` section offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabMyOffers"
        params = _parse_load_js_params(resp)
        self._parse_metadata(soup, resp, params)
        self._parse_my_offers_dom(soup, resp)
        return self

    def parseBuyUnits(self, viewData: Union[str, AjaxResponse]) -> "BlackMarket":
        """Parse a ``tabBuyUnits`` section if provided offline."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabBuyUnits"
        self._parse_buy_units_dom(soup)
        return self

    async def loadAllTabs(self) -> "BlackMarket":
        """Refresh ``view=blackMarket`` (all tabs are inline in one response)."""
        await self.load()
        return self

    def _resolve_offer_unit(self, unitOrId: Union[int, str, Unit]) -> BlackMarketUnitOption:
        """Resolve a unit ID, name, or ``Unit`` against loaded Black Market options."""
        if isinstance(unitOrId, Unit):
            uid = unitOrId.id
            match = next((o for o in self.unitOptions if o.unitId == uid), None)
        elif isinstance(unitOrId, int) and not isinstance(unitOrId, bool):
            match = next((o for o in self.unitOptions if o.unitId == unitOrId), None)
        else:
            parsed = parse_int(str(unitOrId))
            if parsed is not None and str(parsed) == str(unitOrId).strip():
                match = next((o for o in self.unitOptions if o.unitId == parsed), None)
            else:
                needle = str(unitOrId).strip().lower().replace("_", " ")
                match = next(
                    (
                        o
                        for o in self.unitOptions
                        if o.name.lower().replace("_", " ") == needle
                    ),
                    None,
                )
        if match is None:
            raise ValueError(f"Unknown Black Market unit option: {unitOrId!r}")
        return match

    async def offerUnits(
        self,
        unitId: Union[int, str, Unit],
        amount: int,
        currency: Union[int, str, Resource],
        pricePerUnit: int,
    ) -> "BlackMarket":
        """Create a unit sale offer on the Black Market."""
        if not self.isLoaded:
            await self.load()
        if self.isMarketBlocked or self.cooldownActive:
            raise ValueError(
                f"BlackMarket@{self.cityId} cannot post offers right now "
                f"(blocked={self.isMarketBlocked}, cooldown={self.cooldownActive})"
            )

        opt = self._resolve_offer_unit(unitId)
        qty = int(amount)
        price = int(pricePerUnit)
        if qty < 1:
            raise ValueError(f"Offer amount must be >= 1, got {qty}")
        if not opt.canOffer or qty > opt.availableAmount:
            raise ValueError(
                f"Cannot offer {qty}x {opt.name} in city {self.cityId} "
                f"(available={opt.availableAmount}, canOffer={opt.canOffer})"
            )

        curr_code = _resolve_currency_code(currency)
        min_p = opt.minPriceGold if curr_code == "5" else opt.minPriceResource
        max_p = opt.maxPriceGold if curr_code == "5" else opt.maxPriceResource
        if (min_p is not None and price < min_p) or (max_p is not None and price > max_p):
            raise ValueError(
                f"Price {price} per {opt.name} is outside allowed range [{min_p}, {max_p}]"
            )

        await self._post_building_action(
            action="BlackMarketAction",
            function="addOffer",
            payloadPost={
                "offerUnit": str(opt.unitId),
                "unitAmount": str(qty),
                "offerResource": curr_code,
                "unitPrice": str(price),
            },
            templateView="blackMarket",
            action_name="BlackMarket.offerUnits",
            metadata={
                "ambrosia_cost": 0,
                "cityId": self.cityId,
                "unitId": opt.unitId,
                "amount": qty,
            },
            refresh=True,
        )
        return self

    async def postOffer(
        self,
        unitId: Union[int, str, Unit],
        amount: int,
        currency: Union[int, str, Resource],
        pricePerUnit: int,
    ) -> "BlackMarket":
        """Post a Black Market unit offer (alias of :meth:`offerUnits`)."""
        return await self.offerUnits(unitId, amount, currency, pricePerUnit)

    async def cancelOffer(self, offerId: int) -> "BlackMarket":
        """Withdraw an active Black Market offer by offer ID."""
        if not self.isLoaded:
            await self.load()
        target_id = int(offerId)
        match = next((o for o in self.myOffers if o.offerId == target_id), None)
        if match is None:
            raise ValueError(
                f"Black Market offer {target_id} was not found in city {self.cityId}"
            )
        cancel_url = (
            match.cancelUrl
            or f"?action=BlackMarketAction&function=removeOffer&offerId={target_id}&cityId={self.cityId}&position={self.position}"
        )
        await self._post_query_url_action(
            cancel_url,
            action_name="BlackMarket.cancelOffer",
            templateView="blackMarket",
            metadata={"ambrosia_cost": 0, "cityId": self.cityId, "offerId": target_id},
            refresh=True,
        )
        return self

    async def buyUnits(self, offerId: int, amount: int) -> Any:
        """Purchase offered units (read-only stub)."""
        ...
