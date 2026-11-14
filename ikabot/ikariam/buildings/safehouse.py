"""Safehouse (Hideout) building model (`view=safehouse`, `buildingId=16`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import (
    AjaxResponse,
    format_feedback,
    has_feedback_error,
    make_soup,
    parse_int,
    parse_query_int,
    parse_query_params,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_duration_seconds,
    parse_view_payload,
)
from ikabot.ikariam.data import Resources

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


async def execute_send_spy(
    client: "IkariamClient",
    target_city_id: int,
    *,
    origin_city_id: Optional[int] = None,
    current_island_id: Optional[int] = None,
    agents: int = 1,
    decoys: int = 0,
    action_name: str = "Safehouse.sendSpy",
) -> AjaxResponse:
    """Open ``view=sendSpy`` for ``target_city_id`` and dispatch spies/decoys."""
    from ikabot.ikariam.city import _collect_form_inputs, _select_city_id

    agent_cnt = int(agents)
    decoy_cnt = int(decoys)
    if agent_cnt <= 0:
        raise ValueError("agents must be >= 1")
    if decoy_cnt < 0:
        raise ValueError("decoys cannot be negative")

    if origin_city_id is not None:
        await _select_city_id(client, int(origin_city_id), action_name=action_name)

    selected_id = (
        int(origin_city_id)
        if origin_city_id is not None
        else (client.selectedDropDownCity.id if client.selectedDropDownCity is not None else None)
    )
    view_params: Dict[str, str] = {
        "view": "sendSpy",
        "destinationCityId": str(int(target_city_id)),
        "templateView": "sendSpy",
        "actionRequest": "REQUESTID",
        "ajax": "1",
    }
    if current_island_id is not None:
        view_params["backgroundView"] = "island"
        view_params["currentIslandId"] = str(int(current_island_id))
    else:
        view_params["backgroundView"] = "city"
        if selected_id is not None:
            view_params["currentCityId"] = str(selected_id)

    view_resp = await client.post_ajax(params=view_params)
    if has_feedback_error(view_resp.feedback) or not view_resp.view_html:
        detail = format_feedback(view_resp.feedback) or "missing sendSpy view"
        raise ValueError(f"Could not open sendSpy for city {target_city_id}: {detail}")

    soup = BeautifulSoup(view_resp.view_html, "html.parser")
    form = soup.select_one("#missionForm") or soup.find("form")
    if form is None:
        raise ValueError(f"Could not find #missionForm in sendSpy for city {target_city_id}")

    payload = _collect_form_inputs(form)
    if selected_id is None:
        for key in payload:
            m_key = re.match(r"spies\[(\d+)\]\[agents\]", key)
            if m_key:
                selected_id = int(m_key.group(1))
                break
    if selected_id is None:
        raise ValueError("Could not determine origin city ID for sendSpy mission")

    agent_key = f"spies[{selected_id}][agents]"
    decoy_key = f"spies[{selected_id}][decoys]"
    if agent_key not in payload:
        raise ValueError(
            f"City {selected_id} has no spy selector in sendSpy form (no available spies?)"
        )
    avail_el = soup.select_one(f"#js_spyCount_{selected_id}")
    avail_spies = parse_int(avail_el.get_text(strip=True)) if avail_el is not None else None
    if avail_spies is not None and agent_cnt + decoy_cnt > avail_spies:
        raise ValueError(
            f"Requested {agent_cnt} agents + {decoy_cnt} decoys from city {selected_id}, "
            f"but only {avail_spies} spies available"
        )

    payload[agent_key] = str(agent_cnt)
    if decoy_key in payload or decoy_cnt > 0:
        payload[decoy_key] = str(decoy_cnt)

    submit_params: Dict[str, str] = {
        "backgroundView": view_params["backgroundView"],
        "templateView": "sendSpy",
        "actionRequest": "REQUESTID",
        "ajax": "1",
    }
    if "currentIslandId" in view_params:
        submit_params["currentIslandId"] = view_params["currentIslandId"]
    elif selected_id is not None:
        submit_params["currentCityId"] = str(selected_id)

    return await client.post_action(
        payloadPost=payload,
        params=submit_params,
        metadata={"ambrosia_cost": 0, "targetCityId": int(target_city_id), "agents": agent_cnt},
        action_name=action_name,
    )


_TRAIN_CAPACITY_RE = re.compile(r"(\d+)")
_SWITCH_TAB_RE = re.compile(r'switchTab\(["\']([^"\']+)["\']\)')
_WS_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    """Collapse internal whitespace cleanly."""
    return _WS_RE.sub(" ", str(value or "")).strip()


@dataclass
class EspionageMission:
    """Spy currently deployed in another city (``Spy on a mission`` box)."""

    spyId: Optional[int] = None
    targetCityId: Optional[int] = None
    targetCityName: str = ""
    targetOwner: str = ""
    riskPercent: Optional[int] = None
    status: str = ""
    missionUrl: Optional[str] = None
    recallUrl: Optional[str] = None


@dataclass
class EspionageReportEntry:
    """Row from ``tabReports`` or ``tabArchive`` (``#espionageReports``)."""

    reportId: Optional[int] = None
    owner: str = ""
    targetCityId: Optional[int] = None
    targetCityName: str = ""
    mission: str = ""
    result: str = ""
    agents: Optional[int] = None
    decoys: Optional[int] = None
    date: str = ""
    reportUrl: Optional[str] = None
    isRead: bool = True


class Safehouse(Building):
    """Ikariam Hideout / Safehouse building model (``view=safehouse``).

    ``view=safehouse`` loads ``#tabSafehouse`` only; ``tabReports`` and
    ``tabArchive`` are fetched lazily as separate remote tabs.
    """

    buildingId: int = 16
    buildingType: str = "safehouse"

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
        self.activeTab: str = "tabSafehouse"
        self.spyCost: Resources = Resources()
        self.spyTrainTimeSeconds: Optional[int] = None
        self.maxSpies: int = 0
        self.spiesInTraining: int = 0
        self.spiesInDefense: int = 0
        self.spiesOnMission: int = 0
        self.canTrainSpy: bool = False
        self.trainStatusText: str = ""
        self.activeMissions: List[EspionageMission] = []
        self.reports: List[EspionageReportEntry] = []
        self.archivedReports: List[EspionageReportEntry] = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse the active Safehouse tab."""
        detected_tab: Optional[str] = None
        for script in soup.select("#mainview script"):
            m = _SWITCH_TAB_RE.search(script.get_text(" "))
            if m:
                detected_tab = m.group(1)
                break
        if detected_tab:
            self.activeTab = detected_tab

        if soup.select_one("#tabReports") is not None and soup.select_one("#tabSafehouse") is None:
            self.activeTab = "tabReports"
            self.reports = self._parse_reports_dom(soup.select_one("#tabReports") or soup)
            return
        if soup.select_one("#tabArchive") is not None and soup.select_one("#tabSafehouse") is None:
            self.activeTab = "tabArchive"
            self.archivedReports = self._parse_reports_dom(soup.select_one("#tabArchive") or soup)
            return

        self.activeTab = "tabSafehouse"
        self._parse_safehouse_tab(soup, resp)

    def _parse_safehouse_tab(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse ``#tabSafehouse`` training cost, spy counts, and active missions."""
        tab = soup.select_one("#tabSafehouse") or soup

        gold_el = tab.select_one("#js_spygold")
        glass_el = tab.select_one("#js_spyglass")
        time_el = tab.select_one("#js_spycompletion")

        gold = parse_int(gold_el.get_text(" ", strip=True)) if gold_el else 0
        crystal = parse_int(glass_el.get_text(" ", strip=True)) if glass_el else 0
        self.spyCost = Resources(
            gold=gold if gold is not None else 0,
            crystal=crystal if crystal is not None else 0,
        )
        self.spyTrainTimeSeconds = (
            parse_duration_seconds(time_el.get_text(" ", strip=True))
            if time_el is not None
            else None
        )

        self.maxSpies = 0
        self.spiesInTraining = 0
        self.spiesInDefense = 0
        self.spiesOnMission = 0

        stats = tab.select_one(".spy_stats_content")
        if stats is not None:
            cap_b = stats.select_one("b")
            if cap_b is not None:
                m_cap = _TRAIN_CAPACITY_RE.search(cap_b.get_text(" ", strip=True))
                if m_cap:
                    self.maxSpies = int(m_cap.group(1))
            for li in stats.select("ul.disc-list li"):
                txt = _clean_text(li.get_text(" ", strip=True))
                m_cnt = _TRAIN_CAPACITY_RE.search(txt)
                if m_cnt is None:
                    continue
                cnt = int(m_cnt.group(1))
                lower = txt.lower()
                if "defence" in lower or "defense" in lower:
                    self.spiesInDefense = cnt
                elif "mission" in lower:
                    self.spiesOnMission = cnt

        in_training = 0
        for blk in soup.select(".unitConstructionBlock"):
            if blk.select_one(".spy_small") is not None or blk.select_one(".army_wrapper") is not None:
                lbl = blk.select_one(".unitcounttextlabel")
                cnt = parse_int(lbl.get_text(" ", strip=True)) if lbl is not None else None
                in_training += cnt if cnt is not None else 1
        self.spiesInTraining = in_training

        if self.spiesInDefense == 0:
            scroll_el = tab.select_one(".scroll_view")
            if scroll_el is not None:
                def_val = parse_int(scroll_el.get_text(" ", strip=True))
                if def_val is not None:
                    self.spiesInDefense = def_val

        right_div = tab.select_one(".content_right")
        spy_input = tab.select_one("#textfield_spy") or tab.select_one("input[name='textfield_spy']")
        train_btn = (
            tab.select_one("#js_safehouseTrainButton")
            or tab.select_one("#buildForm input[type='submit']")
            or tab.select_one("#buildForm a.button")
        )
        self.trainStatusText = _clean_text(right_div.get_text(" ", strip=True)) if right_div else ""
        self.canTrainSpy = spy_input is not None or (
            train_btn is not None
            and "disabled" not in (train_btn.get("class") or [])
            and not train_btn.has_attr("disabled")
        )

        self.activeMissions = self._parse_missions_dom(tab)

    def _parse_missions_dom(self, tab: Tag) -> List[EspionageMission]:
        """Parse any active spy mission entries inside `#tabSafehouse`."""
        missions: List[EspionageMission] = []
        boxes = tab.select(".contentBox01h")
        mission_box: Optional[Tag] = None
        for box in boxes:
            hdr = box.select_one("h3.header")
            if hdr and "mission" in hdr.get_text(" ", strip=True).lower():
                mission_box = box
                break
        if mission_box is None:
            return missions

        for card in mission_box.select(".spyinfo"):
            city_el = card.select_one("li.city")
            user_link = card.select_one("li.user a")
            statuses = [
                _clean_text(el.get_text(" ", strip=True))
                for el in card.select("li.status")
                if _clean_text(el.get_text(" ", strip=True))
            ]
            spy_link = card.select_one("a[href*='spy='], a[href*='spyId=']")
            mission_btn = card.select_one(
                ".missionButton a[href], a[href*='view=spyMissions']:not([href*='retreat=1'])"
            )
            recall_btn = card.select_one(
                ".missionAbort a[href], a[href*='retreat=1'], a[href*='abortInvasion'], a[href*='recall']"
            )
            city_link = city_el.select_one("a[href]") if city_el is not None else None
            send_spies_btn = card.select_one(".missionSendSpies a[href]")
            target_city_id = (
                parse_query_int(city_link.get("href") if city_link else None, "cityId")
                or parse_query_int(mission_btn.get("href") if mission_btn else None, "targetCityId")
                or parse_query_int(recall_btn.get("href") if recall_btn else None, "targetCityId")
                or parse_query_int(send_spies_btn.get("href") if send_spies_btn else None, "destinationCityId")
            )
            spy_href = (
                (mission_btn.get("href") if mission_btn else None)
                or (recall_btn.get("href") if recall_btn else None)
                or (spy_link.get("href") if spy_link else None)
            )
            spy_id = parse_query_int(spy_href, "spy") or parse_query_int(spy_href, "spyId")
            if spy_id is None:
                m_cd = re.search(r"SpyCountDown(\d+)", str(card))
                if m_cd:
                    spy_id = int(m_cd.group(1))
            missions.append(
                EspionageMission(
                    spyId=spy_id,
                    targetCityId=target_city_id,
                    targetCityName=(
                        _clean_text(city_el.get_text(" ", strip=True))
                        if city_el is not None
                        else ""
                    ),
                    targetOwner=(
                        _clean_text(user_link.get_text(" ", strip=True))
                        if user_link is not None
                        else ""
                    ),
                    status=" | ".join(statuses) or _clean_text(card.get_text(" ", strip=True)),
                    missionUrl=str(mission_btn["href"]) if mission_btn and mission_btn.get("href") else None,
                    recallUrl=str(recall_btn["href"]) if recall_btn and recall_btn.get("href") else None,
                )
            )
        if missions:
            return missions

        for row in mission_box.select("table tr"):
            if row.find("th") is not None and row.find("td") is None:
                continue
            if row.select_one("td[colspan]") is not None:
                continue
            tds = row.select("td")
            if not tds:
                continue
            city_link = row.select_one("a[href*='selectCity='], a[href*='cityId=']")
            spy_link = row.select_one("a[href*='spyId=']")
            recall_link = row.select_one("a[href*='recall']")
            missions.append(
                EspionageMission(
                    spyId=parse_query_int(spy_link.get("href") if spy_link else None, "spyId"),
                    targetCityId=(
                        parse_query_int(city_link.get("href"), "selectCity")
                        or parse_query_int(city_link.get("href"), "cityId")
                        if city_link
                        else None
                    ),
                    targetCityName=_clean_text(city_link.get_text(" ", strip=True)) if city_link else "",
                    status=_clean_text(row.get_text(" ", strip=True)),
                    missionUrl=spy_link.get("href") if spy_link else None,
                    recallUrl=recall_link.get("href") if recall_link else None,
                )
            )
        return missions

    def _parse_reports_dom(self, container: Tag) -> List[EspionageReportEntry]:
        """Parse `#espionageReports` rows cleanly (skipping empty placeholder rows)."""
        table = container.select_one("#espionageReports")
        if table is None:
            return []

        entries: List[EspionageReportEntry] = []
        for tr in table.select("tr"):
            if tr.find("th") is not None and tr.find("td") is None:
                continue
            tr_classes = set(tr.get("class") or [])
            if "report" in tr_classes:
                continue
            checkbox = tr.select_one("input[type='checkbox']")
            if checkbox is None and "espionageReports" not in tr_classes:
                continue
            tds = tr.select("td")
            if len(tds) < 6:
                continue

            report_id = parse_int(checkbox.get("value")) if checkbox else None
            if report_id is None and checkbox is not None:
                m_name = re.search(r"deleteId\[(\d+)\]", str(checkbox.get("name") or ""))
                if m_name:
                    report_id = int(m_name.group(1))
            if report_id is None:
                m_tr_id = re.match(r"message(\d+)", str(tr.get("id") or ""))
                if m_tr_id:
                    report_id = int(m_tr_id.group(1))

            report_link = tr.select_one(
                "a[href*='reportId='], a[href*='safehouseReports']"
            )
            report_url = str(report_link["href"]) if report_link and report_link.get("href") else None
            if report_id is None and report_url:
                report_id = parse_query_int(report_url, "reportId")

            # Walk columns dynamically in case Mission has colspan="2" (9 cells instead of 10).
            owner = _clean_text(tds[2].get_text(" ", strip=True)) if len(tds) > 2 else ""
            target_td = tds[3] if len(tds) > 3 else None
            target_city_link = target_td.select_one("a[href]") if target_td else None
            target_city_id = (
                parse_query_int(target_city_link.get("href"), "selectCity")
                or parse_query_int(target_city_link.get("href"), "cityId")
                if target_city_link
                else None
            )
            target_city = _clean_text(target_td.get_text(" ", strip=True)) if target_td else ""
            mission_td = tds[4] if len(tds) > 4 else None
            mission = _clean_text(mission_td.get_text(" ", strip=True)) if mission_td else ""
            col_shift = -1 if (mission_td is not None and parse_int(mission_td.get("colspan")) == 2) else 0
            res_idx = 6 + col_shift
            result_cell = tds[res_idx] if len(tds) > res_idx else tds[-1]
            result = _clean_text(result_cell.get_text(" ", strip=True))
            if not result:
                img = result_cell.select_one("img")
                if img is not None:
                    result = _clean_text(img.get("title") or img.get("alt") or "")
            if report_url is None:
                res_link = result_cell.select_one("a[href]")
                if res_link is not None and res_link.get("href"):
                    report_url = str(res_link["href"])

            def _parse_deployed_count(cell: Optional[Tag]) -> Optional[int]:
                if cell is None:
                    return None
                raw = _clean_text(cell.get_text(" ", strip=True))
                if "/" in raw:
                    return parse_int(raw.split("/")[-1])
                return parse_int(raw)

            agents_td = tds[res_idx + 1] if len(tds) > res_idx + 1 else None
            decoys_td = tds[res_idx + 2] if len(tds) > res_idx + 2 else None
            date_td = tds[res_idx + 3] if len(tds) > res_idx + 3 else None
            agents = _parse_deployed_count(agents_td)
            decoys = _parse_deployed_count(decoys_td)
            date = _clean_text(date_td.get_text(" ", strip=True)) if date_td else ""
            cb_val = str(checkbox.get("value") or "").lower() if checkbox else ""
            is_read = (
                "unread" not in tr_classes
                and "bold" not in tr_classes
                and cb_val != "unread"
            )

            entries.append(
                EspionageReportEntry(
                    reportId=report_id,
                    owner=owner,
                    targetCityId=target_city_id,
                    targetCityName=target_city,
                    mission=mission,
                    result=result,
                    agents=agents,
                    decoys=decoys,
                    date=date,
                    reportUrl=report_url,
                    isRead=is_read,
                )
            )
        return entries

    def parseReports(self, viewData: Union[str, AjaxResponse]) -> "Safehouse":
        """Parse ``activeTab=tabReports`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabReports"
        self.reports = self._parse_reports_dom(soup.select_one("#tabReports") or soup)
        return self

    def parseArchive(self, viewData: Union[str, AjaxResponse]) -> "Safehouse":
        """Parse ``activeTab=tabArchive`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabArchive"
        self.archivedReports = self._parse_reports_dom(soup.select_one("#tabArchive") or soup)
        return self

    async def loadReports(self) -> "Safehouse":
        """Fetch and parse ``activeTab=tabReports``."""
        resp = await self._fetch_view(view="safehouse", activeTab="tabReports")
        return self.parseReports(resp)

    async def loadArchive(self) -> "Safehouse":
        """Fetch and parse ``activeTab=tabArchive``."""
        resp = await self._fetch_view(view="safehouse", activeTab="tabArchive")
        return self.parseArchive(resp)

    async def loadAllTabs(self) -> "Safehouse":
        """Refresh the primary Hideout view plus reports and archive tabs."""
        await self.load()
        await self.loadReports()
        await self.loadArchive()
        return self

    # --- Actions & Remaining Stubs ---

    async def trainSpy(self, amount: int = 1) -> AjaxResponse:
        """Train ``amount`` spies at this Hideout."""
        from ikabot.ikariam.city import _collect_form_inputs, _select_city_id

        count = int(amount)
        if count <= 0:
            raise ValueError("amount must be a positive integer")
        if not self.isLoaded:
            await self.load()

        used = self.spiesInDefense + self.spiesInTraining + self.spiesOnMission
        if self.maxSpies and used + count > self.maxSpies:
            raise ValueError(
                f"Cannot train {count} spies: {used}/{self.maxSpies} capacity already used"
            )
        if not self.canTrainSpy:
            detail = self.trainStatusText or "Hideout training button is unavailable"
            raise ValueError(f"Cannot train spy in city {self.cityId}: {detail}")

        client = self._require_client()
        await _select_city_id(client, self.cityId, action_name="Safehouse.trainSpy")

        payload: Dict[str, Any] = {}
        html = self._last_response.view_html if self._last_response is not None else ""
        if html:
            soup = make_soup(html)
            form = soup.select_one("#buildForm")
            if form is not None:
                payload = _collect_form_inputs(form)
        payload.setdefault("action", "Espionage")
        payload.setdefault("function", "buildSpy")
        payload.setdefault("cityId", str(self.cityId))
        payload.setdefault("position", str(self.position))
        payload["textfield_spy"] = str(count)

        resp = await client.post_action(
            payloadPost=payload,
            params={
                "activeTab": "tabSafehouse",
                "backgroundView": "city",
                "currentCityId": str(self.cityId),
                "templateView": "safehouse",
                "actionRequest": "REQUESTID",
                "ajax": "1",
            },
            metadata={
                "ambrosia_cost": 0,
                "cityId": self.cityId,
                "amount": count,
            },
            action_name="Safehouse.trainSpy",
        )
        if resp.view_html:
            self.parseView(resp)
        else:
            await self.load()
        return resp

    async def sendSpy(
        self,
        targetCityId: int,
        islandId: Optional[int] = None,
        *,
        agents: int = 1,
        decoys: int = 0,
    ) -> AjaxResponse:
        """Dispatch ``agents`` spies (and optional ``decoys``) to ``targetCityId``."""
        client = self._require_client()
        resp = await execute_send_spy(
            client,
            int(targetCityId),
            origin_city_id=self.cityId,
            current_island_id=islandId,
            agents=agents,
            decoys=decoys,
            action_name="Safehouse.sendSpy",
        )
        await self.load()
        return resp

    async def _submit_spy_missions_form(
        self,
        mission_url: str,
        *,
        mission_type: Optional[Union[int, str]] = None,
        agents: Optional[int] = None,
        decoys: int = 0,
        pay_city_id: Optional[int] = None,
        action_name: str,
    ) -> AjaxResponse:
        """Open ``view=spyMissions`` and submit an espionage or stationed-recall order."""
        from ikabot.ikariam.city import _collect_form_inputs, _select_city_id

        client = self._require_client()
        await _select_city_id(client, self.cityId, action_name=action_name)

        params = parse_query_params(mission_url)
        params.setdefault("view", "spyMissions")
        params["backgroundView"] = "city"
        params["currentCityId"] = str(self.cityId)
        params["templateView"] = "spyMissions"
        params["actionRequest"] = "REQUESTID"
        params["ajax"] = "1"

        view_resp = await client.post_ajax(params=params)
        if has_feedback_error(view_resp.feedback) or not view_resp.view_html:
            detail = format_feedback(view_resp.feedback) or "missing spyMissions view"
            raise ValueError(f"Could not open spyMissions view: {detail}")

        soup = BeautifulSoup(view_resp.view_html, "html.parser")
        form = soup.select_one("#missionForm") or soup.find("form")
        if form is None:
            raise ValueError("Could not find #missionForm in spyMissions view")

        payload = _collect_form_inputs(form)
        mission_select = form.select_one("select[name='mission']")
        resolved_mission = payload.get("mission") or ""
        if mission_select is not None:
            options = mission_select.find_all("option")
            if mission_type is None:
                selected_opt = next((o for o in options if o.has_attr("selected")), None)
                resolved_mission = str(selected_opt.get("value")) if selected_opt else resolved_mission
            else:
                req_str = str(mission_type).strip()
                exact = next((o for o in options if str(o.get("value")) == req_str), None)
                if exact is None:
                    lower_req = req_str.lower()
                    exact = next(
                        (o for o in options if lower_req in o.get_text(" ", strip=True).lower()),
                        None,
                    )
                if exact is None or exact.get("value") is None:
                    avail = [(o.get("value"), o.get_text(" ", strip=True)) for o in options]
                    raise ValueError(f"Unknown espionage mission {mission_type!r} (available: {avail})")
                resolved_mission = str(exact["value"])
        elif mission_type is not None:
            resolved_mission = str(mission_type)

        avail_el = soup.select_one(f"#js_spyCount_{self.cityId}")
        stationed = parse_int(avail_el.get_text(strip=True)) if avail_el is not None else None
        decoy_cnt = int(decoys)
        if decoy_cnt < 0:
            raise ValueError("decoys cannot be negative")
        if agents is None:
            agent_cnt = stationed if stationed and stationed > 0 else 1
        else:
            agent_cnt = int(agents)
        if agent_cnt <= 0:
            raise ValueError("agents must be >= 1")
        if stationed is not None and agent_cnt + decoy_cnt > stationed:
            raise ValueError(
                f"Requested {agent_cnt} agents + {decoy_cnt} decoys, but only {stationed} stationed"
            )

        payload["mission"] = resolved_mission
        payload[f"spies[{self.cityId}][agents]"] = str(agent_cnt)
        payload[f"spies[{self.cityId}][decoys]"] = str(decoy_cnt)
        payload["payCityId"] = str(int(pay_city_id if pay_city_id is not None else self.cityId))

        resp = await client.post_action(
            payloadPost=payload,
            params={
                "backgroundView": "city",
                "currentCityId": str(self.cityId),
                "templateView": "spyMissions",
                "actionRequest": "REQUESTID",
                "ajax": "1",
            },
            metadata={
                "ambrosia_cost": 0,
                "mission": resolved_mission,
                "targetCityId": parse_int(payload.get("targetCity")),
            },
            action_name=action_name,
        )
        await self.load()
        return resp

    def _find_active_mission(
        self,
        identifier: int,
        *,
        require_attr: str,
    ) -> Optional[EspionageMission]:
        """Find a matching active mission by ``spyId`` or ``targetCityId``."""
        sid = int(identifier)
        for m in self.activeMissions:
            if (m.spyId == sid or m.targetCityId == sid) and getattr(m, require_attr):
                return m
        return None

    async def spyMission(
        self,
        spyId: int,
        missionType: Union[int, str],
        *,
        agents: int = 1,
        decoys: int = 0,
        payCityId: Optional[int] = None,
    ) -> AjaxResponse:
        """Order deployed spies (matched by ``targetCityId`` or ``spyId``) to run ``missionType``."""
        if not self.isLoaded:
            await self.load()
        mission = self._find_active_mission(spyId, require_attr="missionUrl")
        if mission is None:
            await self.load()
            mission = self._find_active_mission(spyId, require_attr="missionUrl")
        if mission is None or not mission.missionUrl:
            raise ValueError(f"No stationed spy mission controls found for {spyId}")
        return await self._submit_spy_missions_form(
            mission.missionUrl,
            mission_type=missionType,
            agents=agents,
            decoys=decoys,
            pay_city_id=payCityId,
            action_name="Safehouse.spyMission",
        )

    async def recallSpy(
        self,
        spyId: int,
        *,
        agents: Optional[int] = None,
    ) -> AjaxResponse:
        """Recall a spy en route (``abortInvasion``) or stationed in a town (``mission=8``)."""
        sid = int(spyId)
        if not self.isLoaded:
            await self.load()
        mission = self._find_active_mission(sid, require_attr="recallUrl")
        if mission is None:
            await self.load()
            mission = self._find_active_mission(sid, require_attr="recallUrl")
        if mission is None or not mission.recallUrl:
            raise ValueError(f"Spy/target {sid} was not found with a recall URL in activeMissions")
        if "view=spyMissions" in mission.recallUrl:
            return await self._submit_spy_missions_form(
                mission.recallUrl,
                mission_type="8",
                agents=agents,
                decoys=0,
                action_name="Safehouse.recallSpy",
            )
        return await self._post_query_url_action(
            mission.recallUrl,
            action_name="Safehouse.recallSpy",
            templateView="safehouse",
            metadata={"ambrosia_cost": 0, "spyId": sid},
        )

    async def deleteReports(self, reportIds: List[int]) -> AjaxResponse:
        """Delete selected espionage reports from ``#tabReports``."""
        ids = [int(rid) for rid in reportIds]
        if not ids:
            raise ValueError("Must specify at least one espionage report ID to delete")
        if not self.reports or self.activeTab != "tabReports":
            await self.loadReports()

        payload: Dict[str, Any] = {
            "offset": "0",
            "actionType": "666",
        }
        by_id = {r.reportId: r for r in self.reports if r.reportId is not None}
        for rid in ids:
            entry = by_id.get(rid)
            payload[f"deleteId[{rid}]"] = "read" if (entry and entry.isRead) else "unread"

        resp = await self._post_building_action(
            action="Espionage",
            function="processReports",
            payloadPost=payload,
            extraParams={"activeTab": "tabReports"},
            templateView="safehouse",
            metadata={"ambrosia_cost": 0, "reportIds": ids},
            action_name="Safehouse.deleteReports",
            refresh=False,
        )
        if resp.view_html and "espionageReports" in resp.view_html:
            self.parseReports(resp)
        else:
            await self.loadReports()
        return resp

    async def archiveReports(self, reportIds: List[int]) -> Any:
        """Archive selected espionage reports (requires Ambrosia/Premium; stub)."""
        ...
