from datetime import datetime
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Union

from ikabot.config import materials_names_english, miracle_names_english
from ikabot.ikariam._parsing import (
    AjaxResponse,
    Table,
    TableCell,
    TableRow,
    Tag,
    decode_unicode_escape,
    extract_ajax_responder,
    make_soup,
    parse_ajax_response,
    parse_float,
    parse_int,
    parse_query_int,
)
from ikabot.ikariam.city import IslandCity, IslandPlace, _submit_unit_mission_form
from ikabot.ikariam.data import (
    MiracleDonationTableRow,
    Resource,
    ResourceDonationTableRow,
    Resources,
    Unit,
    Units,
)
from ikabot.ikariam.player import AvatarScore

if TYPE_CHECKING:
    from ikabot.ikariam.client import Client


def _extract_donate_form(
    view_html: str,
    *,
    island_id: int,
    template_view: str,
) -> Tuple[Tag, Dict[str, str]]:
    """Parse ``#donateForm`` hidden inputs and standard island AJAX parameters."""
    soup = make_soup(view_html)
    form = soup.find('form', id='donateForm')
    if form is None:
        raise RuntimeError(
            'Donate form is unavailable; ensure an own city on this island is selected '
            'before opening this island view.'
        )
    payload: Dict[str, str] = {}
    for inp in form.find_all('input'):
        name = inp.get('name')
        if not name:
            continue
        if (inp.get('type') or '').lower() == 'hidden':
            payload[str(name)] = str(inp.get('value') or '')
    payload.setdefault('islandId', str(island_id))
    payload['backgroundView'] = 'island'
    payload['currentIslandId'] = str(island_id)
    payload['templateView'] = template_view
    payload['actionRequest'] = 'REQUESTID'
    payload['ajax'] = '1'
    return form, payload


def _extract_first_int(text: Optional[str]) -> Optional[int]:
    """Extract the first formatted integer token from ``text``."""
    if not text:
        return None
    match = re.search(r'-?\d(?:[\d.,\xa0\u202f]*\d)?', text)
    if not match:
        return None
    return parse_int(match.group(0))


def _parse_donation_player_cell(
    cell: TableCell,
    prev_row: Optional[Union[ResourceDonationTableRow, MiracleDonationTableRow]],
) -> Tuple[str, str, int]:
    """Extract ``(playerFlagTag, playerName, playerId)`` from a donation table player cell."""
    flag_span = cell.tag.find('span', class_='flag')
    if flag_span is not None:
        flag_classes = [cls for cls in (flag_span.get('class') or []) if cls != 'flag']
        player_flag_tag = flag_classes[0] if flag_classes else (prev_row.playerFlagTag if prev_row else '')
    else:
        player_flag_tag = prev_row.playerFlagTag if prev_row else ''

    name_span = cell.tag.find('span', class_='avatarName')
    if name_span is not None:
        player_name = name_span.get_text(strip=True)
    else:
        player_name = prev_row.playerName if prev_row else ''

    link = cell.tag.find('a', href=True)
    parsed_id = parse_query_int(link.get('href'), 'avatarId') if link is not None else None
    player_id = parsed_id if parsed_id is not None else (prev_row.playerId if prev_row else 0)

    return player_flag_tag, player_name, player_id


def _resolve_donated(
    cell_text: str,
    player_id: int,
    prev_row: Optional[Union[ResourceDonationTableRow, MiracleDonationTableRow]],
) -> int:
    """Parse donated amount from ``cell_text``, inheriting from ``prev_row`` for multi-city players."""
    parsed = _extract_first_int(cell_text)
    if parsed is not None:
        return parsed
    if prev_row is not None and player_id == prev_row.playerId:
        return prev_row.donated
    return 0


def _parse_tooltip_int(template_data: dict, key: str, as_float: bool = True) -> int:
    """Parse a numeric or percentage tooltip value from ``updateTemplateData``."""
    entry = template_data.get(key)
    raw = entry.get('text') if isinstance(entry, dict) else entry
    if raw is None:
        return 0
    if not as_float:
        if isinstance(raw, str) and re.search(r'[.,]\d{1,2}$', raw.strip()):
            val = parse_float(raw)
            return int(val) if val is not None else 0
        parsed_int = parse_int(raw)
        if parsed_int is not None:
            return parsed_int
    val = parse_float(raw)
    return int(val) if val is not None else 0


def _parse_upgrade_timestamp(value: Any) -> Optional[datetime]:
    """Convert an Ikariam end-upgrade unix timestamp to ``datetime`` when active."""
    ts = parse_int(value)
    return datetime.fromtimestamp(ts) if ts is not None and ts > 0 else None


def _extract_unit_id_from_cell(cell: TableCell) -> Optional[int]:
    """Extract the Ikariam unit ID from a ``militaryList`` header cell's ``s<id>`` class."""
    for div in cell.tag.find_all('div'):
        for cls in div.get('class') or []:
            if cls.startswith('s') and cls[1:].isdigit():
                return int(cls[1:])
    return None


class WorldMapIsland:
    """Island object that contains data about an island as returned by the World Map View."""

    x: int
    y: int
    id: int
    name: str
    luxuryResourceType: int
    luxuryResourceName: str
    miracleType: int
    miracleName: str
    woodLevel: int
    cityCount: int
    isRed: Optional[bool]  # will be None if data is from full island view
    isBlue: Optional[bool]  # will be None if data is from full island view
    inRangeOfPiracy: bool
    hasHelios: bool
    hasAlly: bool
    hasCityOccupiedByAlly: bool
    hasOwnCity: bool
    hasCityOccupiedBySelf: bool
    hasTreaty: bool
    isWarIsland: bool

    def __init__(self, client: 'Client', x: int, y: int, data: Union[list, dict]) -> None:
        """Initialize a :class:`WorldMapIsland` from world map coordinates and island array data."""
        self._client = client
        self.x = int(x)
        self.y = int(y)
        self._loadWorldMapFlags(client)

        self.id = int(data[0])
        self.name = decode_unicode_escape(str(data[1]))
        self.luxuryResourceType = int(data[2])
        self.luxuryResourceName = materials_names_english[self.luxuryResourceType]
        self.miracleType = int(data[3])
        self.miracleName = miracle_names_english[self.miracleType]
        self.woodLevel = int(data[6])
        self.cityCount = int(data[7])
        self.inRangeOfPiracy = bool(int(data[8]))
        self.hasHelios = bool(int(data[9]))
        self.isRed = bool(int(data[10]))
        self.isBlue = bool(int(data[11]))

        self.__world_map_data = data

    def _loadWorldMapFlags(self, client: 'Client') -> None:
        """Populate island relationship flags from ``client.additionalWorldMapData``."""
        additional = getattr(client, 'additionalWorldMapData', None) or {}
        coords = (self.x, self.y)
        flag_keys = (
            ('hasAlly', 'allyIslandJS'),
            ('hasCityOccupiedByAlly', 'occupiedIslandAllyJS'),
            ('hasOwnCity', 'ownIslandJS'),
            ('hasCityOccupiedBySelf', 'occupiedIslandJS'),
            ('hasTreaty', 'militaryIslandsJS'),
            ('isWarIsland', 'warIslandsJS'),
        )
        for attr, key in flag_keys:
            setattr(self, attr, coords in additional.get(key, []))

    async def getIsland(self) -> 'Island':
        """Fetch and return the full :class:`Island` object for this island."""
        html = await self._client.get(f'view=island&islandId={self.id}')
        commands = extract_ajax_responder(html)
        bg_data = parse_ajax_response(commands).background_data
        if bg_data is None:
            raise ValueError(f'Missing updateBackgroundData for island {self.id}')
        return Island(self._client, bg_data)


class ResourceDonationTable(Table):
    """Donation and worker allocation table from a sawmill or luxury mine view."""

    resourceView: 'ResourceView'
    rows: List[ResourceDonationTableRow]

    def __init__(self, resourceView: 'ResourceView', tableHTML: Union[str, Tag]) -> None:
        """Parse the resource donation table HTML into :class:`ResourceDonationTableRow` entries."""
        self.resourceView = resourceView
        super().__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            if len(row._cells) < 5:
                continue
            cells = row._cells
            prev_row = self.rows[-1] if self.rows else None
            player_flag_tag, player_name, player_id = _parse_donation_player_cell(cells[0], prev_row)
            player_city_name = cells[1].text
            player_city_level = _extract_first_int(cells[2].text) or 0
            player_city_workers = _extract_first_int(cells[3].text) or 0
            donated = _resolve_donated(cells[4].text, player_id, prev_row)

            self.rows.append(
                ResourceDonationTableRow(
                    player_flag_tag,
                    player_name,
                    player_id,
                    player_city_name,
                    player_city_level,
                    player_city_workers,
                    donated,
                )
            )


class ResourceView:
    """View representing an island sawmill (wood) or luxury resource mine."""

    island: 'Island'
    sliderMaxSkilledWorkers: int
    sliderMaxUnskilledWorkers: int
    sliderMaxWorkers: int
    sliderCurrentWorkers: int
    citizensAvailable: int
    basicProduction: int
    unskilledWorkersProduction: int
    serverProductionBonusPercent: int
    premiumProductionBonusPercent: int
    adVideoProductionBonusPercent: int
    heliosTowerProductionBonusPercent: int
    godProductionBonusPercent: int
    totalProduction: int
    canDonate: bool
    maxDonation: int

    requiredForNextLevel: int
    availableDonated: int

    donationTable: ResourceDonationTable

    def __init__(self, island: 'Island', updateTemplateData: dict, viewData: str) -> None:
        """Initialize a :class:`ResourceView` from ``updateTemplateData`` and ``viewData`` HTML."""
        self.island = island

        slider = (updateTemplateData.get('js_ResourceSlider') or {}).get('slider') or {}
        self.sliderMaxSkilledWorkers = parse_int(slider.get('max_value')) or 0
        self.sliderMaxUnskilledWorkers = parse_int(slider.get('overcharge')) or 0
        self.sliderMaxWorkers = self.sliderMaxSkilledWorkers + self.sliderMaxUnskilledWorkers
        self.sliderCurrentWorkers = parse_int(slider.get('ini_value')) or 0
        self.citizensAvailable = parse_int(updateTemplateData.get('valueCitizens')) or 0

        self.basicProduction = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_basic_production')
        self.unskilledWorkersProduction = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_overload_production')
        self.serverProductionBonusPercent = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_server_production_bonus')
        self.premiumProductionBonusPercent = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_premium_production_bonus')
        self.adVideoProductionBonusPercent = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_adVideo_production_bonus')
        self.heliosTowerProductionBonusPercent = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_helios_tower_bonus')
        self.godProductionBonusPercent = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_god_bonus')
        self.totalProduction = _parse_tooltip_int(updateTemplateData, 'js_resource_tooltip_total_production', as_float=False)

        raw_params = (updateTemplateData.get('load_js') or {}).get('params', '{}')
        load_params = json.loads(raw_params) if isinstance(raw_params, str) else (raw_params or {})
        self.canDonate = bool(load_params.get('canDonate', False))
        self.maxDonation = parse_int(load_params.get('maxDonation')) or 0

        soup = make_soup(viewData)
        wood_elements = soup.find_all(class_='wood')
        self.requiredForNextLevel = (
            (parse_int(wood_elements[0].get_text(strip=True)) or 0) if len(wood_elements) > 0 else 0
        )
        self.availableDonated = (
            (parse_int(wood_elements[1].get_text(strip=True)) or 0) if len(wood_elements) > 1 else 0
        )

        self.donationTable = ResourceDonationTable(self, updateTemplateData.get('donationTableContainer', ''))

        workers_form = soup.find('form', id='setWorkers')
        form_type = None
        form_city_id: Optional[int] = None
        if workers_form is not None:
            t_in = workers_form.find('input', attrs={'name': 'type'})
            c_in = workers_form.find('input', attrs={'name': 'cityId'})
            form_type = str(t_in.get('value')) if t_in and t_in.get('value') else None
            form_city_id = parse_int(c_in.get('value')) if c_in else None
        if form_type is None:
            form_type = str(updateTemplateData.get('type') or ('resource' if workers_form and workers_form.find('input', attrs={'name': 'rw'}) else 'tradegood'))
        if form_city_id is None and self.island._client.selectedDropDownCity is not None:
            form_city_id = self.island._client.selectedDropDownCity.id
        self._resource_type = form_type
        self._worker_city_id = form_city_id

        self.__luxury_resource_view_template_data = updateTemplateData
        self.__luxury_resource_view_view_data = viewData

    async def setWorkers(self, workers: int) -> 'ResourceView':
        """Set the number of workers assigned to this resource."""
        if not self._worker_city_id:
            raise ValueError('Cannot set workers: no own city ID available in ResourceView form')
        worker_key = 'rw' if self._resource_type == 'resource' else 'tw'
        await self.island._client.post_action(
            params={
                'islandId': str(self.island.id),
                'cityId': str(self._worker_city_id),
                'type': self._resource_type,
                'screen': self._resource_type,
                'action': 'IslandScreen',
                'function': 'workerPlan',
                worker_key: str(int(workers)),
                'backgroundView': 'island',
                'currentIslandId': str(self.island.id),
                'templateView': self._resource_type,
                'actionRequest': 'REQUESTID',
            },
            action_name='ResourceView.setWorkers',
        )
        fresh = await self.island._getResourceView(self._resource_type)
        self.__dict__.update(fresh.__dict__)
        return self

    async def donateWood(self, wood: int) -> None:
        """Donate ``wood`` toward upgrading this island resource."""
        amount = int(wood)
        if amount <= 0:
            raise ValueError('Donation amount must be a positive integer.')
        if not self.canDonate:
            raise ValueError('Donations are not currently allowed for this island resource.')
        if self.maxDonation is not None and amount > self.maxDonation:
            raise ValueError(
                f'Donation amount {amount} exceeds maximum allowed ({self.maxDonation}).'
            )

        form, payload = _extract_donate_form(
            self.__luxury_resource_view_view_data,
            island_id=self.island.id,
            template_view=self._resource_type,
        )
        resource_type = payload.get('type') or self._resource_type or 'resource'
        payload['type'] = resource_type
        payload['templateView'] = resource_type
        payload.setdefault('action', 'IslandScreen')
        payload.setdefault('function', 'donate')
        if form.find('input', attrs={'name': 'donation'}) is None:
            raise RuntimeError('Donation input field is missing from #donateForm.')
        payload['donation'] = str(amount)

        await self.island._client.post_action(
            payloadPost=payload,
            metadata={'type': resource_type, 'islandId': self.island.id, 'wood': amount},
            action_name=f'ResourceView.donateWood({self.island.id}, {amount})',
        )
        fresh = await self.island._getResourceView(resource_type)
        self.__dict__.update(fresh.__dict__)


class MiracleDonationTable(Table):
    """Donation and priest conversion table from an island miracle view."""

    miracleView: 'MiracleView'
    rows: List[MiracleDonationTableRow]

    def __init__(self, miracleView: 'MiracleView', tableHTML: Union[str, Tag]) -> None:
        """Parse the miracle donation table HTML into :class:`MiracleDonationTableRow` entries."""
        self.miracleView = miracleView
        super().__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            if len(row._cells) < 6:
                continue
            cells = row._cells
            prev_row = self.rows[-1] if self.rows else None
            player_flag_tag, player_name, player_id = _parse_donation_player_cell(cells[0], prev_row)
            player_city_name = cells[1].text
            donated = _resolve_donated(cells[2].text, player_id, prev_row)
            priests = _extract_first_int(cells[3].text) or 0
            conversion_percent = parse_float(cells[4].text) or 0.0
            conversion_island_share_percent = parse_float(cells[5].text) or 0.0

            self.rows.append(
                MiracleDonationTableRow(
                    player_flag_tag,
                    player_name,
                    player_id,
                    player_city_name,
                    donated,
                    priests,
                    conversion_percent,
                    conversion_island_share_percent,
                )
            )


MiracleDontaionTable = MiracleDonationTable


class MiracleView:
    """View representing an island miracle (wonder), faith status, and donations."""

    island: 'Island'
    faithPercentage: int
    faithLevel: int
    requiredForNextLevel: Optional[int]
    availableDonated: Optional[int]
    donationTable: MiracleDonationTable

    def __init__(self, island: 'Island', updateTemplateData: dict, viewData: str) -> None:
        """Initialize a :class:`MiracleView` from ``updateTemplateData`` and ``viewData`` HTML."""
        self.island = island
        soup = make_soup(viewData)

        belief_info = str(updateTemplateData.get('wonderBeliefInfo2') or '')
        self.faithPercentage = _extract_first_int(belief_info) or 0

        level_val = updateTemplateData.get('wonderLevelDisplay')
        if isinstance(level_val, dict):
            level_val = level_val.get('text')
        faith_level = parse_int(level_val)
        if faith_level is None:
            level_el = soup.find(id='wonderLevelDisplay')
            faith_level = parse_int(level_el.get_text(strip=True)) if level_el else None
        self.faithLevel = faith_level if faith_level is not None else 0

        next_level_val = updateTemplateData.get('js_donateNextLevel')
        if isinstance(next_level_val, dict):
            next_level_val = next_level_val.get('text')
        self.requiredForNextLevel = parse_int(next_level_val)

        donated_val = updateTemplateData.get('js_donatedResources')
        if isinstance(donated_val, dict):
            donated_val = donated_val.get('text')
        self.availableDonated = parse_int(donated_val)

        tables = soup.find_all('table')
        donation_table_tag: Union[Tag, str] = next(
            (
                table
                for table in tables
                if table.find('a', href=lambda href: href and ('avatarProfile' in href or 'sortBy=donation' in href))
            ),
            tables[1] if len(tables) > 1 else (tables[0] if tables else ''),
        )
        self.donationTable = MiracleDonationTable(self, donation_table_tag)

        self.__miracle_view_template_data = updateTemplateData
        self.__miracle_view_view_data = viewData

    async def donate(
        self,
        wine: int = 0,
        crystal: int = 0,
        sulphur: int = 0,
        *,
        marble: int = 0,
    ) -> None:
        """Donate luxury resources toward upgrading this island's miracle."""
        amounts_by_field = (
            ('tradegood1', 'wine', int(wine)),
            ('tradegood2', 'marble', int(marble)),
            ('tradegood3', 'crystal', int(crystal)),
            ('tradegood4', 'sulphur', int(sulphur)),
        )
        for _, label, amount in amounts_by_field:
            if amount < 0:
                raise ValueError(f'Miracle donation amount for {label} cannot be negative.')
        if not any(amount > 0 for _, _, amount in amounts_by_field):
            raise ValueError('At least one luxury resource donation amount must be positive.')

        form, payload = _extract_donate_form(
            self.__miracle_view_view_data,
            island_id=self.island.id,
            template_view='wonder',
        )
        payload.setdefault('action', 'IslandScreen')
        payload.setdefault('function', 'wonderDonate')

        available_fields = {
            str(inp.get('name'))
            for inp in form.find_all('input')
            if inp.get('name') and (inp.get('type') or '').lower() in ('text', 'number', '')
        }
        for field_name, label, amount in amounts_by_field:
            if field_name in available_fields:
                payload[field_name] = str(amount)
            elif amount > 0:
                raise ValueError(
                    f'Miracle on island {self.island.id} does not accept {label} donations.'
                )

        await self.island._client.post_action(
            payloadPost=payload,
            metadata={
                'islandId': self.island.id,
                'wine': int(wine),
                'marble': int(marble),
                'crystal': int(crystal),
                'sulphur': int(sulphur),
            },
            action_name=f'MiracleView.donate({self.island.id})',
        )
        fresh = await self.island.getMiracleView()
        self.__dict__.update(fresh.__dict__)


class BarbarianVillageView:
    """View representing the barbarian village's resources, defending army, and actions."""

    barbarianVillage: 'BarbarianVillage'
    isPillagable: bool
    revengeProbability: Optional[str]  # Optional because there is no revenge up to level 10
    resources: List[Resource]
    units: List[Unit]
    wallLevel: Optional[int]  # No wall up to level 10

    def __init__(self, barbarianVillage: 'BarbarianVillage', updateTemplateData: dict, viewData: str) -> None:
        """Initialize a :class:`BarbarianVillageView` from ``updateTemplateData`` and ``viewData`` HTML."""
        self.barbarianVillage = barbarianVillage
        plundering = updateTemplateData.get('js_islandBarbarianPlundering') or {}
        self.isPillagable = plundering.get('href') not in ('javascript:void(0);', '')

        revenge = updateTemplateData.get('barbarianKingRevenge')
        self.revengeProbability = revenge.get('text') if isinstance(revenge, dict) else revenge

        resource_specs = (
            ('js_islandBarbarianResourcegold', Resources.Gold),
            ('js_islandBarbarianResourceresource', Resources.Wood),
            ('js_islandBarbarianResourcetradegood1', Resources.Wine),
            ('js_islandBarbarianResourcetradegood2', Resources.Marble),
            ('js_islandBarbarianResourcetradegood3', Resources.Crystal),
            ('js_islandBarbarianResourcetradegood4', Resources.Sulphur),
        )
        self.resources = [
            resource_cls(parse_int((updateTemplateData.get(key) or {}).get('text')) or 0)
            for key, resource_cls in resource_specs
        ]

        self.wallLevel = None
        self.units = []
        soup = make_soup(viewData)
        military_table_tag = soup.find('table', class_='militaryList')
        if military_table_tag is not None:
            military_table = Table(military_table_tag)
            for idx in range(0, len(military_table._rows) - 1, 2):
                header_cells = military_table._rows[idx]._cells
                count_cells = military_table._rows[idx + 1]._cells
                for header_cell, count_cell in zip(header_cells, count_cells):
                    unit_id = _extract_unit_id_from_cell(header_cell)
                    if unit_id is None:
                        continue
                    count_val = _extract_first_int(count_cell.text)
                    if count_val is None:
                        continue
                    if unit_id == 314:
                        self.wallLevel = count_val
                    else:
                        unit_template = Units.getUnitById(unit_id)
                        if unit_template is not None:
                            self.units.append(unit_template(count_val))

        self.__barbarian_village_view_template_data = updateTemplateData
        self.__barbarian_village_view_view_data = viewData

    async def pillage(
        self,
        units: Union[
            Sequence[Unit],
            Dict[Union[int, str, Unit], int],
            Sequence[Tuple[Union[int, str, Unit], int]],
        ],
        transporters: int = 0,
        *,
        originCityId: Optional[int] = None,
    ) -> AjaxResponse:
        """Send a pillage attack against this barbarian village."""
        client = self.barbarianVillage.island._client
        if originCityId is not None:
            city_obj = await client.getCity(originCityId)
            await city_obj._ensure_selected()
            if not self.isPillagable:
                refreshed = await self.barbarianVillage.getBarbarianVillageView()
                self.isPillagable = refreshed.isPillagable
                self.__barbarian_village_view_template_data = (
                    refreshed.__barbarian_village_view_template_data
                )

        if not self.isPillagable:
            raise ValueError(
                f"Barbarian village on island {self.barbarianVillage.island.id} cannot be pillaged right now"
            )

        plundering = (
            self.__barbarian_village_view_template_data.get("js_islandBarbarianPlundering") or {}
        )
        plunder_href = str(plundering.get("href") or "")
        params = {
            "view": "plunder",
            "destinationCityId": "0",
            "barbarianVillage": "1",
            "islandId": str(self.barbarianVillage.island.id),
            "backgroundView": "island",
            "currentIslandId": str(self.barbarianVillage.island.id),
            "templateView": "plunder",
            "actionRequest": "REQUESTID",
            "ajax": "1",
        }
        if plunder_href:
            # Ensure origin island pillage link parameters match the active village.
            params["islandId"] = str(parse_query_int(plunder_href, "islandId") or self.barbarianVillage.island.id)
        view_resp = await client.post_ajax(params=params)
        if not view_resp.view_html:
            raise ValueError(
                f"Could not open barbarian village plunder view on island {self.barbarianVillage.island.id}"
            )
        return await _submit_unit_mission_form(
            client,
            view_resp.view_html,
            units,
            transporters=transporters,
            origin_city_id=originCityId,
            action_name="BarbarianVillageView.pillage",
        )

    async def ceaseFire(self) -> None:
        """Request or accept a ceasefire with the barbarian village."""
        ...

    async def shadyMerchant(self) -> None:
        """Open or interact with the shady merchant in the barbarian village."""
        ...


class BarbarianVillage:
    """Barbarian village object. ``kingName`` and ``isDestroyed`` will be ``None`` on foreign islands."""

    island: 'Island'
    name: str
    visible: bool
    numberOfBarbarians: int
    wallLevel: int
    level: int
    isUnderAttack: bool
    isLuxuryResourceSiege: bool
    kingName: Optional[str]
    isDestroyed: Optional[bool]

    def __init__(self, island: 'Island', data: dict) -> None:
        """Initialize a :class:`BarbarianVillage` from the island's ``barbarians`` dictionary."""
        self.island = island
        self.name = 'Barbarian Village'
        self.visible = parse_int(data.get('invisible', 1)) == 0
        self.numberOfBarbarians = parse_int(data.get('count')) or 0
        self.wallLevel = parse_int(data.get('wallLevel')) or 0
        self.level = parse_int(data.get('level')) or 0
        self.isUnderAttack = parse_int(data.get('underAttack')) == 1
        self.isLuxuryResourceSiege = parse_int(data.get('isTradegoodSiege')) == 1
        self.kingName = data.get('city')
        if 'destroyed' in data and data['destroyed'] is not None:
            self.isDestroyed = parse_int(data['destroyed']) == 1
        else:
            self.isDestroyed = None

        self.__barbarian_village_data = data

    @property
    def _island(self) -> 'Island':
        """Return the owning :class:`Island`."""
        return self.island

    async def getBarbarianVillageView(self) -> BarbarianVillageView:
        """Fetch and return the detailed :class:`BarbarianVillageView`."""
        island_id = str(self._island.id)
        resp = await self._island._client.post_ajax(
            params={
                'view': 'barbarianVillage',
                'destinationIslandId': island_id,
                'oldBackgroundView': 'island',
                'islandId': island_id,
                'backgroundView': 'island',
                'currentIslandId': island_id,
                'actionRequest': 'REQUESTID',
                'ajax': '1',
            }
        )
        return BarbarianVillageView(self, resp.template_data, resp.view_html or '')


class HeliosTower:
    """Helios tower state on an island. ``ownerName`` is ``None`` if not built."""

    island: 'Island'
    isBuilt: bool
    top: int
    mid: int
    base: int
    name: str
    tooltip: str
    isActive: bool
    ownerName: Optional[str]

    def __init__(self, island: 'Island', data: dict) -> None:
        """Initialize a :class:`HeliosTower` from full island background data."""
        self.island = island
        self.isBuilt = bool(data.get('isHeliosTowerBuilt', False))
        self.top = parse_int(data.get('heliosTop')) or 0
        self.mid = parse_int(data.get('heliosMid')) or 0
        self.base = parse_int(data.get('heliosBase')) or 0
        self.name = decode_unicode_escape(data.get('heliosName'))
        self.tooltip = str(data.get('heliosTooltip') or '')
        self.isActive = parse_int(data.get('heliosActive')) == 1
        self.ownerName = self.name.rsplit("'", 1)[0] if self.isBuilt and "'" in self.name else None

        self.__helios_tower_data = data


class Island(WorldMapIsland):
    """Island object that contains full data about an island from the island view.

    ``isRed`` and ``isBlue`` will be ``None``, as that data is only returned by the
    world map and not by the detailed island view.
    """

    luxuryResourceLevel: int
    miracleLevel: int
    woodBonusActive: bool
    luxuryResourceBonusActive: bool
    luxuryResourceEndUpgradeTime: Optional[datetime]
    woodEndUpgradeTime: Optional[datetime]
    miracleEndUpgradeTime: Optional[datetime]
    heliosTower: HeliosTower
    barbarianVillage: BarbarianVillage
    avatarScores: List[AvatarScore]
    islandPlaces: List[Union[IslandCity, IslandPlace]]

    def __init__(self, client: 'Client', data: dict) -> None:
        """Initialize an :class:`Island` from Ikariam ``updateBackgroundData`` payload."""
        self._client = client
        self.x = int(data['xCoord'])
        self.y = int(data['yCoord'])
        self.id = int(data['id'])
        self.name = decode_unicode_escape(str(data.get('name', '')))
        self.luxuryResourceType = int(data['tradegood'])
        self.luxuryResourceName = materials_names_english[self.luxuryResourceType]
        self.miracleType = int(data['wonder'])
        self.miracleName = miracle_names_english[self.miracleType]
        self.woodLevel = int(data['resourceLevel'])
        self.isRed = None
        self.isBlue = None
        self.hasHelios = bool(data.get('isHeliosTowerBuilt', False))
        self._loadWorldMapFlags(client)

        self.luxuryResourceLevel = int(data['tradegoodLevel'])
        self.miracleLevel = int(data['wonderLevel'])
        self.woodBonusActive = parse_int(data.get('showResourceBonusIcon')) == 1
        self.luxuryResourceBonusActive = parse_int(data.get('showTradegoodBonusIcon')) == 1
        self.luxuryResourceEndUpgradeTime = _parse_upgrade_timestamp(data.get('tradegoodEndUpgradeTime'))
        self.woodEndUpgradeTime = _parse_upgrade_timestamp(data.get('resourceEndUpgradeTime'))
        self.miracleEndUpgradeTime = _parse_upgrade_timestamp(data.get('wonderEndUpgradeTime'))
        self.heliosTower = HeliosTower(self, data)
        self.barbarianVillage = BarbarianVillage(self, data.get('barbarians') or {})

        raw_scores = data.get('avatarScores')
        score_values = raw_scores.values() if isinstance(raw_scores, dict) else ()
        self.avatarScores = [AvatarScore(score) for score in score_values]

        self.islandPlaces = []
        for pos, islandSpot in enumerate(data.get('cities') or []):
            spot_type = islandSpot.get('type')
            if spot_type == 'city':
                self.islandPlaces.append(IslandCity(self, pos, islandSpot))
            elif spot_type in ('buildplace', 'empty'):
                self.islandPlaces.append(IslandPlace(self, pos, islandSpot))

        cities = self.getCities()
        self.cityCount = len(cities)
        self.inRangeOfPiracy = any(city.isPiracyRaidable for city in cities)

        self.__island_data = data

    def getCities(self) -> List[IslandCity]:
        """Return all populated :class:`IslandCity` instances on this island."""
        return [place for place in self.islandPlaces if type(place) is IslandCity]

    def getEmptyPlaces(self) -> List[IslandPlace]:
        """Return all empty :class:`IslandPlace` building spots on this island."""
        return [place for place in self.islandPlaces if type(place) is IslandPlace]

    async def _getResourceView(self, view: str) -> ResourceView:
        """Fetch and return a :class:`ResourceView` for ``view`` (``'resource'`` or ``'tradegood'``)."""
        resp = await self._client.post_ajax(
            params={
                'view': view,
                'type': view,
                'islandId': str(self.id),
                'ajax': '1',
            }
        )
        return ResourceView(self, resp.template_data, resp.view_html or '')

    async def getLuxuryResourceView(self) -> ResourceView:
        """Fetch and return the luxury resource mine :class:`ResourceView`."""
        # TODO prevent clicking this if it's upgrading, that's gonna cause issues 100%
        return await self._getResourceView('tradegood')

    async def getWoodResourceView(self) -> ResourceView:
        """Fetch and return the sawmill (wood) :class:`ResourceView`."""
        # TODO prevent clicking this if it's upgrading, that's gonna cause issues 100%
        return await self._getResourceView('resource')

    async def getMiracleView(self) -> MiracleView:
        """Fetch and return the island miracle :class:`MiracleView`."""
        resp = await self._client.post_ajax(
            params={
                'view': 'wonder',
                'islandId': str(self.id),
                'ajax': '1',
            }
        )
        return MiracleView(self, resp.template_data, resp.view_html or '')
