"""Async Ikariam client, global state parser, and game view models."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import inspect
import re
import time
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    overload,
)
from urllib.parse import parse_qs

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import (
    AjaxResponse,
    Table,
    decode_unicode_escape,
    extract_ajax_responder,
    extract_js_json_parse,
    extract_js_json_string,
    format_feedback,
    has_feedback_error,
    make_soup,
    parse_ajax_response,
    parse_float,
    parse_int,
    parse_query_int,
    parse_query_params,
)
from ikabot.ikariam.advisors import (
    CombatInProgressEntry,
    CombatReportEntry,
    CombatReportsView,
    DiplomacyAgoraView,
    DiplomacyAllianceInfoView,
    DiplomacyAllianceMembersView,
    DiplomacyAllianceView,
    DiplomacyMessage,
    DiplomacyTreatiesView,
    DiplomacyView,
    MayorMessageTable,
    MayorView,
    MilitaryTable,
    MilitaryView,
    OccupiedLocation,
    ResearchArea,
    ResearchDetail,
    ResearchEntry,
    ResearchPrecondition,
    ResearchView,
    TownCulturalStatus,
    TradeRouteEntry,
    TradeRoutesView,
    WarEntry,
    WarsView,
)
from ikabot.ikariam.city import City, DropdownCity
from ikabot.ikariam.data import (
    AllianceHighScoreTableRow,
    AllianceHighScoreTypes,
    HighScoreTypes,
    PlayerHighScoreTableRow,
)
from ikabot.ikariam.island import Island, WorldMapIsland
from ikabot.web.session import Session

_WORLD_MAP_KEYS = (
    'occupiedIslandJS',
    'occupiedIslandAllyJS',
    'allyIslandJS',
    'ownIslandJS',
    'militaryIslandsJS',
    'warIslandsJS',
    'barbarianIslandsJS',
)

_VACATION_ICON_RE = re.compile(r'b325e463b9e55ec28ebd4f87a87593')

_BLOCKED_AMBROSIA_ACTIONS = frozenset(
    {
        'AmbrosiaFountainActions',
        'SpeedupDailyTask',
    }
)
_BLOCKED_AMBROSIA_FUNCTIONS = frozenset(
    {
        'modifyReportArchive',
        'accelerateLoading',
        'buyPhoenicianTransporter',
        'buyPhoenicianFreighter',
        'activateTradeRoute',
        'createTradeRoute',
        'activateSafeCapacityBonus',
        'activateStorageCapacityBonus',
    }
)
_AMBROSIA_FLAG_KEYS = (
    'payWithAmbrosia',
    'useAmbrosia',
    'buyWithAmbrosia',
    'finishWithAmbrosia',
)
_TRUTHY_FLAG_IGNORE = frozenset({'', '0', 'false', 'no', 'none', 'null'})


class IkariamActionError(RuntimeError):
    """Raised when Ikariam rejects an in-game action or returns malformed action feedback."""

    def __init__(
        self,
        message: str,
        *,
        ajax_response: Optional[AjaxResponse] = None,
    ) -> None:
        super().__init__(message)
        self.ajax_response = ajax_response


class AmbrosiaBlockedError(IkariamActionError):
    """Raised when a client hook blocks an Ambrosia-spending request."""


@dataclass
class RequestContext:
    """Mutable outbound HTTP request envelope passed to ``before_request`` hooks."""

    method: Literal['GET', 'POST']
    url: str = ''
    params: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    isAjax: bool = False
    kwargs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponseContext:
    """Inbound HTTP response envelope passed to ``after_request`` hooks."""

    request: RequestContext
    raw: str
    ajax: Optional[AjaxResponse] = None
    elapsedSeconds: float = 0.0
    error: Optional[BaseException] = None


BeforeRequestHook = Callable[
    [RequestContext],
    Union[Optional[RequestContext], Awaitable[Optional[RequestContext]]],
]
AfterRequestHook = Callable[
    [ResponseContext],
    Union[Optional[str], Awaitable[Optional[str]]],
]


def _merged_request_fields(ctx: RequestContext) -> Dict[str, Any]:
    """Combine query-string parameters from ``url``, ``params``, and ``payload``."""
    merged: Dict[str, Any] = {}
    merged.update(parse_query_params(ctx.url))
    merged.update(ctx.params)
    merged.update(ctx.payload)
    return merged


def zero_ambrosia_guard(ctx: RequestContext) -> None:
    """Block requests that spend Ambrosia or invoke Ambrosia-gated game actions."""
    ambrosia_cost = ctx.metadata.get('ambrosia_cost', 0)
    if isinstance(ambrosia_cost, (int, float)) and ambrosia_cost > 0:
        raise AmbrosiaBlockedError(
            f'Blocked request with ambrosia_cost={ambrosia_cost}: '
            f"{ctx.metadata.get('action_name') or ctx.url}"
        )

    merged = _merged_request_fields(ctx)
    for flag_key in _AMBROSIA_FLAG_KEYS:
        if flag_key in merged:
            flag_val = merged[flag_key]
            if isinstance(flag_val, bool):
                if flag_val:
                    raise AmbrosiaBlockedError(f'Blocked Ambrosia flag {flag_key}=True')
            elif str(flag_val).strip().lower() not in _TRUTHY_FLAG_IGNORE:
                raise AmbrosiaBlockedError(
                    f'Blocked Ambrosia flag {flag_key}={flag_val!r}'
                )

    action = str(merged.get('action') or '')
    function = str(merged.get('function') or '')

    if action in _BLOCKED_AMBROSIA_ACTIONS:
        raise AmbrosiaBlockedError(f'Blocked Ambrosia action={action!r}')

    if function in _BLOCKED_AMBROSIA_FUNCTIONS:
        raise AmbrosiaBlockedError(f'Blocked Ambrosia function={function!r}')

    if function == 'extendGracePeriod' and ctx.metadata.get('ambrosia_cost') != 0:
        raise AmbrosiaBlockedError(
            'Blocked extendGracePeriod without proven zero-Ambrosia item cost'
        )

    if action == 'Premium':
        if function == 'buildingSpeedup':
            if ctx.metadata.get('ambrosia_cost') != 0:
                raise AmbrosiaBlockedError(
                    'Blocked Premium/buildingSpeedup without proven free (<5m) ambrosia_cost=0'
                )
            return
        if function == 'editTradeRoute':
            renew_val = str(merged.get('renew', '0')).strip().lower()
            create_val = str(merged.get('create', '0')).strip().lower()
            if renew_val not in ('0', '', 'false', 'none') or create_val not in (
                '0',
                '',
                'false',
                'none',
            ):
                raise AmbrosiaBlockedError(
                    f'Blocked Premium/editTradeRoute with renew={renew_val!r}, create={create_val!r}'
                )
            return
        raise AmbrosiaBlockedError(
            f'Blocked Premium action={action!r}, function={function!r}'
        )


def validate_ajax_action(
    resp: AjaxResponse,
    action_name: str = '',
) -> AjaxResponse:
    """Validate an action ``AjaxResponse`` and raise :class:`IkariamActionError` on failure."""
    label = action_name or 'Action'
    if not resp.commands:
        raise IkariamActionError(f'{label} returned empty AJAX response', ajax_response=resp)

    if has_feedback_error(resp.feedback):
        detail = format_feedback(resp.feedback) or 'server error feedback'
        raise IkariamActionError(f'{label} failed: {detail}', ajax_response=resp)

    for cmd in resp.commands:
        if (
            isinstance(cmd, list)
            and len(cmd) >= 2
            and cmd[0] == 'custom'
            and isinstance(cmd[1], list)
            and cmd[1]
            and cmd[1][0] in ('logout', 'error')
        ):
            raise IkariamActionError(f'{label} rejected by server custom event: {cmd[1][0]}', ajax_response=resp)

    return resp


def _empty_world_map_data() -> Dict[str, List[Tuple[int, int]]]:
    """Return an empty world-map coordinate overlay mapping."""
    return {key: [] for key in _WORLD_MAP_KEYS}


def _parse_json_int(value: Any, *, round_float: bool = False) -> Optional[int]:
    """Parse an integer from a raw JSON number or unlocalized numeric string."""
    parsed = parse_float(value)
    if parsed is None:
        return None
    return round(parsed) if round_float else int(parsed)


def _extract_background_data(response: str, context: str) -> dict:
    """Extract ``updateBackgroundData`` from either an HTML page or ``ajax=1`` payload."""
    if response.lstrip().startswith('['):
        parsed = parse_ajax_response(response)
    else:
        parsed = parse_ajax_response(extract_ajax_responder(response))
    if parsed.background_data is None:
        raise ValueError(f'Missing updateBackgroundData for {context}')
    return parsed.background_data


def _parse_highscore_selects(
    soup: BeautifulSoup,
) -> Tuple[str, List[Tuple[int, int]], Optional[int]]:
    """Parse highscore type, available page ranges, and selected offset from select controls."""
    current_score_type = HighScoreTypes.totalScore
    score_select = soup.find('select', attrs={'name': 'highscoreType'})
    if score_select is not None:
        options = score_select.find_all('option')
        selected_opt = next((opt for opt in options if opt.has_attr('selected')), None)
        if selected_opt is None and options:
            selected_opt = options[0]
        if selected_opt is not None and selected_opt.get('value') is not None:
            current_score_type = str(selected_opt['value'])

    available_ranges: List[Tuple[int, int]] = []
    selected_offset: Optional[int] = None
    offset_select = soup.find('select', attrs={'name': 'offset'})
    if offset_select is not None:
        for opt in offset_select.find_all('option'):
            range_start = parse_int(opt.get('value'))
            if range_start is None:
                continue
            if range_start >= 0:
                available_ranges.append((range_start + 1, range_start + 50))
            if opt.has_attr('selected'):
                selected_offset = range_start if range_start >= 0 else None

    return current_score_type, available_ranges, selected_offset


def _compute_range_bounds(
    rows: List[Any],
    selected_offset: Optional[int],
) -> Tuple[int, int]:
    """Compute displayed ``(start, end)`` rank bounds, guarding empty tables."""
    if not rows:
        return 0, 0
    first_pos = rows[0].position
    last_pos = rows[-1].position
    start = (
        first_pos
        if first_pos is not None
        else ((selected_offset + 1) if selected_offset is not None else 1)
    )
    end = last_pos if last_pos is not None else (start + len(rows) - 1)
    return start, end


def _extract_range_offset(*args: Any, **kwargs: Any) -> int:
    """Resolve the 0-based Ikariam highscore offset from ``getRange`` arguments."""
    if args:
        first = args[0]
        start = first[0] if isinstance(first, tuple) else int(first)
    elif 'range' in kwargs:
        start = kwargs['range'][0]
    elif 'start' in kwargs:
        start = int(kwargs['start'])
    else:
        raise TypeError('getRange() requires a (start, end) tuple or start, end integers')
    return max(0, start - 1)


def _extract_flag_tag(cell_tag: Tag) -> str:
    """Extract the country/visibility flag class from a ``span.flag`` element."""
    flag_span = cell_tag.find('span', class_='flag')
    if flag_span is None:
        return ''
    return next((cls for cls in (flag_span.get('class') or []) if cls != 'flag'), '')


class Client:
    """Async Ikariam client managing serialized requests and global game state."""

    session: Session
    ambrosia: Optional[int]
    gold: Optional[int]
    income: Optional[int]
    badTaxAccountant: Optional[int]
    plutusGold: Optional[int]
    scientistsUpkeep: Optional[int]
    upkeep: Optional[int]
    totalIncome: Optional[int]
    premiumGoldBonusPercent: Optional[int]
    ikariamVersion: Optional[str]
    freeTransporters: Optional[int]
    maxTransporters: Optional[int]
    freeFreighters: Optional[int]
    maxFreighters: Optional[int]

    serverName: Optional[str]
    userId: Optional[int]
    allianceId: Optional[int]
    hasPremiumAccount: Optional[bool]
    additionalWorldMapData: Dict[str, List[Tuple[int, int]]]

    mayorStatus: Optional[str]
    militaryStatus: Optional[str]
    researchStatus: Optional[str]
    diplomacyStatus: Optional[str]

    dropDownCities: List[DropdownCity]
    selectedDropDownCity: Optional[DropdownCity]

    def __init__(self, session: Session, *, blockAmbrosia: bool = True) -> None:
        """Initialize client state with empty defaults, request lock, and hook pipelines."""
        self.session = session
        self._request_lock = asyncio.Lock()
        self._worldMapJsonData: Optional[dict] = None
        self.blockAmbrosia: bool = blockAmbrosia
        self._before_request_hooks: List[BeforeRequestHook] = []
        self._after_request_hooks: List[AfterRequestHook] = []
        if blockAmbrosia:
            self._before_request_hooks.append(zero_ambrosia_guard)

        self.ambrosia = None
        self.gold = None
        self.income = None
        self.badTaxAccountant = None
        self.plutusGold = None
        self.scientistsUpkeep = None
        self.upkeep = None
        self.totalIncome = None
        self.premiumGoldBonusPercent = None
        self.ikariamVersion = None
        self.freeTransporters = None
        self.maxTransporters = None
        self.freeFreighters = None
        self.maxFreighters = None

        self.serverName = None
        self.userId = None
        self.allianceId = None
        self.hasPremiumAccount = None
        self.additionalWorldMapData = _empty_world_map_data()

        self.mayorStatus = None
        self.militaryStatus = None
        self.researchStatus = None
        self.diplomacyStatus = None

        self.dropDownCities = []
        self.selectedDropDownCity = None

    @classmethod
    async def create(
        cls,
        session: Session,
        *,
        blockAmbrosia: bool = True,
    ) -> 'Client':
        """Construct a :class:`Client` and perform its initial ``refresh()``."""
        client = cls(session, blockAmbrosia=blockAmbrosia)
        await client.refresh()
        return client

    def add_before_request_hook(self, hook: BeforeRequestHook) -> BeforeRequestHook:
        """Register a sync or async callable invoked before every request hits ``session``."""
        if hook not in self._before_request_hooks:
            self._before_request_hooks.append(hook)
        return hook

    def remove_before_request_hook(self, hook: BeforeRequestHook) -> None:
        """Remove a previously registered ``before_request`` hook if present."""
        self._before_request_hooks = [
            existing for existing in self._before_request_hooks if existing != hook
        ]

    def add_after_request_hook(self, hook: AfterRequestHook) -> AfterRequestHook:
        """Register a sync or async callable invoked after every session response."""
        if hook not in self._after_request_hooks:
            self._after_request_hooks.append(hook)
        return hook

    def remove_after_request_hook(self, hook: AfterRequestHook) -> None:
        """Remove a previously registered ``after_request`` hook if present."""
        self._after_request_hooks = [
            existing for existing in self._after_request_hooks if existing != hook
        ]

    async def __aenter__(self) -> 'Client':
        """Enter async context manager, refreshing global state if not yet loaded."""
        if self.serverName is None:
            await self.refresh()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager cleanly."""
        return None

    async def refresh(self) -> 'Client':
        """Fetch ``view=worldmap_iso`` to refresh global state and world-map data."""
        await self.get('view=worldmap_iso')
        return self

    @staticmethod
    async def _call_hook(hook: Callable[..., Any], arg: Any) -> Any:
        """Invoke a sync or async hook callback and await any returned awaitable."""
        if inspect.iscoroutinefunction(hook):
            return await hook(arg)
        result = hook(arg)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _invoke_transport(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call a sync or async session transport function on an executor thread when needed."""
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        result = await asyncio.to_thread(func, *args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _request(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """Execute a raw session callable under ``_request_lock`` and update global state."""
        async with self._request_lock:
            response = await self._invoke_transport(func, *args, **kwargs)
            if isinstance(response, str):
                self.__load_global_data(response)
            return response

    async def request(
        self,
        method: Literal['GET', 'POST'],
        url: str = '',
        *,
        params: Optional[dict] = None,
        payload: Optional[dict] = None,
        is_ajax: bool = False,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> str:
        """Send a serialized GET or POST request through ``before`` / ``after`` hooks."""
        ctx = RequestContext(
            method=method,
            url=url,
            params=dict(params or {}),
            payload=dict(payload or {}),
            isAjax=is_ajax,
            kwargs=dict(kwargs),
            metadata=dict(metadata or {}),
        )
        async with self._request_lock:
            # Snapshot hooks so callbacks do not corrupt iteration order if mutated.
            for before_hook in list(self._before_request_hooks):
                updated_ctx = await self._call_hook(before_hook, ctx)
                if isinstance(updated_ctx, RequestContext):
                    ctx = updated_ctx

            clean_url = ctx.url.lstrip('?') if ctx.url.startswith('?') else ctx.url
            started = time.monotonic()
            response: Any = ''
            error: Optional[BaseException] = None
            ajax_obj: Optional[AjaxResponse] = None

            try:
                if ctx.method == 'GET':
                    response = await self._invoke_transport(
                        self.session.get,
                        clean_url,
                        params=dict(ctx.params),
                        **ctx.kwargs,
                    )
                elif ctx.method == 'POST':
                    response = await self._invoke_transport(
                        self.session.post,
                        clean_url,
                        payloadPost=dict(ctx.payload),
                        params=dict(ctx.params),
                        **ctx.kwargs,
                    )
                else:
                    raise ValueError(f'Unsupported HTTP method: {ctx.method!r}')

                if isinstance(response, str):
                    self.__load_global_data(response)
                    if ctx.isAjax or response.lstrip().startswith('['):
                        try:
                            ajax_obj = parse_ajax_response(response)
                        except ValueError:
                            ajax_obj = None
            except BaseException as exc:
                error = exc

            elapsed = time.monotonic() - started
            res_ctx = ResponseContext(
                request=ctx,
                raw=response if isinstance(response, str) else '',
                ajax=ajax_obj,
                elapsedSeconds=elapsed,
                error=error,
            )
            for after_hook in list(self._after_request_hooks):
                hook_result = await self._call_hook(after_hook, res_ctx)
                if error is None and isinstance(hook_result, str):
                    response = hook_result
                    res_ctx.raw = hook_result

            if error is not None:
                raise error
            return response

    async def post(
        self,
        url: str = '',
        payloadPost: Optional[dict] = None,
        params: Optional[dict] = None,
        *,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> str:
        """Send a serialized POST request through ``self.session`` and return the body."""
        return await self.request(
            'POST',
            url,
            params=params,
            payload=payloadPost,
            is_ajax=False,
            metadata=metadata,
            **kwargs,
        )

    async def get(
        self,
        url: str = '',
        params: Optional[dict] = None,
        *,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> str:
        """Send a serialized GET request through ``self.session`` and return the body."""
        return await self.request(
            'GET',
            url,
            params=params,
            is_ajax=False,
            metadata=metadata,
            **kwargs,
        )

    async def get_ajax(
        self,
        url: str = '',
        params: Optional[dict] = None,
        *,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> AjaxResponse:
        """Send a GET request with ``ajax=1`` and return a parsed :class:`AjaxResponse`."""
        merged_params = dict(params or {})
        merged_params['ajax'] = '1'
        resp = await self.request(
            'GET',
            url,
            params=merged_params,
            is_ajax=True,
            metadata=metadata,
            **kwargs,
        )
        return parse_ajax_response(resp)

    async def post_ajax(
        self,
        url: str = '',
        payloadPost: Optional[dict] = None,
        params: Optional[dict] = None,
        *,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> AjaxResponse:
        """Send a POST request with ``ajax=1`` and return a parsed :class:`AjaxResponse`."""
        merged_params = dict(params or {})
        merged_params['ajax'] = '1'
        payload = dict(payloadPost or {})
        resp = await self.request(
            'POST',
            url,
            params=merged_params,
            payload=payload,
            is_ajax=True,
            metadata=metadata,
            **kwargs,
        )
        return parse_ajax_response(resp)

    @staticmethod
    def _merge_action_params(
        url: str,
        params: Optional[dict],
        payload: Optional[dict],
    ) -> Tuple[str, Dict[str, Any]]:
        """Extract query parameters from ``url`` cleanly and ensure ``actionRequest``."""
        merged: Dict[str, Any] = {}
        clean_url = url
        if url and ('=' in url or '?' in url):
            merged.update(parse_query_params(url, normalize_action_request=True))
            clean_url = ''
        if params:
            merged.update(params)
        if 'actionRequest' not in merged and not (payload and 'actionRequest' in payload):
            merged['actionRequest'] = 'REQUESTID'
        elif merged.get('actionRequest') and merged['actionRequest'] != 'REQUESTID':
            # Replace stale parsed page tokens so the active session injects the latest token.
            merged['actionRequest'] = 'REQUESTID'
        return clean_url, merged

    async def post_action(
        self,
        url: str = '',
        *,
        payloadPost: Optional[dict] = None,
        params: Optional[dict] = None,
        metadata: Optional[dict] = None,
        action_name: str = '',
        raise_on_error: bool = True,
        **kwargs: Any,
    ) -> AjaxResponse:
        """Send an in-game AJAX action POST, inject ``actionRequest``, and validate feedback."""
        clean_url, merged_params = self._merge_action_params(url, params, payloadPost)
        meta = dict(metadata or {})
        if action_name and 'action_name' not in meta:
            meta['action_name'] = action_name
        resp = await self.post_ajax(
            clean_url,
            payloadPost=payloadPost,
            params=merged_params,
            metadata=meta,
            **kwargs,
        )
        if raise_on_error:
            validate_ajax_action(resp, action_name=action_name or str(meta.get('action_name') or ''))
        return resp

    async def get_action(
        self,
        url: str = '',
        *,
        params: Optional[dict] = None,
        metadata: Optional[dict] = None,
        action_name: str = '',
        raise_on_error: bool = True,
        **kwargs: Any,
    ) -> AjaxResponse:
        """Send an in-game AJAX action GET (e.g. direct ``href`` link) and validate feedback."""
        clean_url, merged_params = self._merge_action_params(url, params, None)
        meta = dict(metadata or {})
        if action_name and 'action_name' not in meta:
            meta['action_name'] = action_name
        resp = await self.get_ajax(
            clean_url,
            params=merged_params,
            metadata=meta,
            **kwargs,
        )
        if raise_on_error:
            validate_ajax_action(resp, action_name=action_name or str(meta.get('action_name') or ''))
        return resp

    def _load_advisor_statuses(self, advisor_data: dict) -> None:
        """Update advisor highlight classes and premium flag from advisor metadata."""
        if 'military' in advisor_data and isinstance(advisor_data['military'], dict):
            self.militaryStatus = advisor_data['military'].get('cssclass')
        if 'cities' in advisor_data and isinstance(advisor_data['cities'], dict):
            self.mayorStatus = advisor_data['cities'].get('cssclass')
        if 'research' in advisor_data and isinstance(advisor_data['research'], dict):
            self.researchStatus = advisor_data['research'].get('cssclass')
        if 'diplomacy' in advisor_data and isinstance(advisor_data['diplomacy'], dict):
            self.diplomacyStatus = advisor_data['diplomacy'].get('cssclass')
        if 'hasPremiumAccount' in advisor_data:
            self.hasPremiumAccount = bool(advisor_data['hasPremiumAccount'])

    def _load_related_cities(self, related_cities: dict) -> None:
        """Populate ``dropDownCities`` and ``selectedDropDownCity`` from city menu data."""
        selected_key = related_cities.get('selectedCity')
        self.dropDownCities = []
        self.selectedDropDownCity = None
        for key, value in related_cities.items():
            if key.startswith('city_') and isinstance(value, dict):
                city_obj = DropdownCity(self, value)
                self.dropDownCities.append(city_obj)
                if selected_key == key:
                    self.selectedDropDownCity = city_obj

    def _load_global_data_from_ajax(self, response: str) -> None:
        """Update global header, advisor, and city-dropdown fields from an ``ajax=1`` response."""
        ajax_resp = parse_ajax_response(response)
        global_data = ajax_resp.global_data
        if not global_data:
            return
        header = global_data.get('headerData')
        if not isinstance(header, dict):
            return

        int_fields = {
            'ambrosia': ('ambrosia', False),
            'gold': ('gold', False),
            'freeTransporters': ('freeTransporters', False),
            'maxTransporters': ('maxTransporters', False),
            'freeFreighters': ('freeFreighters', False),
            'maxFreighters': ('maxFreighters', False),
            'scientistsUpkeep': ('scientistsUpkeep', False),
            'income': ('income', True),
            'upkeep': ('upkeep', False),
            'godGoldResult': ('plutusGold', False),
            'badTaxAccountant': ('badTaxAccountant', False),
        }
        for header_key, (attr_name, round_float) in int_fields.items():
            if header_key in header:
                parsed = _parse_json_int(header.get(header_key), round_float=round_float)
                if parsed is not None:
                    setattr(self, attr_name, parsed)

        if any(
            key in header
            for key in ('income', 'scientistsUpkeep', 'upkeep', 'godGoldResult', 'badTaxAccountant')
        ):
            self.totalIncome = (
                (self.income or 0)
                + (self.scientistsUpkeep or 0)
                + (self.upkeep or 0)
                + (self.plutusGold or 0)
                + (self.badTaxAccountant or 0)
            )

        advisors = header.get('advisors')
        if isinstance(advisors, dict):
            self._load_advisor_statuses(advisors)

        city_menu = header.get('cityDropdownMenu')
        if isinstance(city_menu, dict):
            self._load_related_cities(city_menu)

    def _load_global_data_from_html(self, html: str) -> None:
        """Update global state, account metadata, and world-map caches from full HTML."""
        soup = make_soup(html)

        selector_attr_map = (
            ('#headlineAmbrosia', 'ambrosia'),
            ('#js_GlobalMenu_freeTransporters', 'freeTransporters'),
            ('#js_GlobalMenu_maxTransporters', 'maxTransporters'),
            ('#js_GlobalMenu_freeFreighters', 'freeFreighters'),
            ('#js_GlobalMenu_maxFreighters', 'maxFreighters'),
            ('#js_GlobalMenu_gold_Total', 'gold'),
            ('#js_GlobalMenu_income', 'income'),
            ('#js_GlobalMenu_badTaxAccountant', 'badTaxAccountant'),
            ('#js_GlobalMenu_godGoldResult', 'plutusGold'),
            ('#js_GlobalMenu_scientistsUpkeep', 'scientistsUpkeep'),
            ('#js_GlobalMenu_upkeep', 'upkeep'),
            ('#js_GlobalMenu_gold_Calculation', 'totalIncome'),
        )
        for selector, attr_name in selector_attr_map:
            element = soup.select_one(selector)
            if element is not None:
                parsed = parse_int(element.get_text(strip=True))
                if parsed is not None:
                    setattr(self, attr_name, parsed)

        bonus_el = soup.select_one('#js_GlobalMenu_production_gold_premiumBonus_value')
        if bonus_el is not None:
            parsed_bonus = parse_int(bonus_el.get_text(strip=True).replace('%', ''))
            if parsed_bonus is not None:
                self.premiumGoldBonusPercent = parsed_bonus

        version_el = soup.select_one('a[href="?view=version"]')
        if version_el is not None:
            version_text = version_el.get_text(strip=True).lstrip('v').strip()
            if version_text:
                self.ikariamVersion = version_text

        for script in soup.find_all('script'):
            script_text = script.string or script.get_text() or ''
            if 'dataSetForView' in script_text:
                server_match = re.search(
                    r"\bserverName\s*:\s*(['\"])((?:\\.|(?!\1).)*)\1",
                    script_text,
                )
                if server_match:
                    self.serverName = server_match.group(2).replace("\\'", "'").replace('\\"', '"')

                user_match = re.search(r"\bavatarId\s*:\s*['\"]?(\d+)['\"]?", script_text)
                if user_match:
                    self.userId = parse_int(user_match.group(1))

                ally_match = re.search(
                    r"\bavatarAllyId\s*:\s*['\"]?([^'\",}\s]*)['\"]?",
                    script_text,
                )
                if ally_match:
                    raw_ally = ally_match.group(1).strip()
                    if raw_ally in ('', '0'):
                        self.allianceId = None
                    else:
                        parsed_ally = parse_int(raw_ally)
                        self.allianceId = parsed_ally if parsed_ally else None

                advisor_data = extract_js_json_parse(script_text, 'advisorData')
                if isinstance(advisor_data, dict):
                    self._load_advisor_statuses(advisor_data)

                if not (isinstance(advisor_data, dict) and 'hasPremiumAccount' in advisor_data):
                    premium_match = re.search(
                        r"\bhasPremiumAccount\s*:\s*(['\"]?)([^'\",\s}]*)\1",
                        script_text,
                    )
                    if premium_match:
                        raw_premium = premium_match.group(2).strip().lower()
                        self.hasPremiumAccount = raw_premium not in ('', '0', 'false', 'null', 'none')

                related_cities = extract_js_json_parse(script_text, 'relatedCityData')
                if isinstance(related_cities, dict):
                    self._load_related_cities(related_cities)

            if any(f'{key} =' in script_text or f'{key}[' in script_text for key in _WORLD_MAP_KEYS):
                world_data = _empty_world_map_data()
                for key in _WORLD_MAP_KEYS:
                    coords = re.findall(rf"\b{key}\[(\d+)\]\[(\d+)\]\s*=\s*1", script_text)
                    world_data[key] = [(int(x), int(y)) for x, y in coords]
                self.additionalWorldMapData = world_data

            if 'jsonData' in script_text:
                json_data = extract_js_json_string(script_text, 'jsonData')
                if isinstance(json_data, dict):
                    self._worldMapJsonData = json_data

    def __load_global_data(self, response: str) -> None:
        """Dispatch global state extraction for either ``ajax=1`` JSON or HTML responses."""
        if not response:
            return
        if response.lstrip().startswith('['):
            self._load_global_data_from_ajax(response)
        else:
            self._load_global_data_from_html(response)

    async def getWorldMapIslands(self) -> List[WorldMapIsland]:
        """Return :class:`WorldMapIsland` objects from cached or freshly loaded world-map data."""
        if self._worldMapJsonData is None:
            await self.refresh()
        data_map = (self._worldMapJsonData or {}).get('data') or {}
        islands: List[WorldMapIsland] = []
        for x_str, y_map in data_map.items():
            if not isinstance(y_map, dict):
                continue
            for y_str, tile_data in y_map.items():
                islands.append(WorldMapIsland(self, int(x_str), int(y_str), tile_data))
        return islands

    async def getIsland(self, islandId: int) -> Island:
        """Fetch and return full :class:`Island` data for ``islandId``."""
        html = await self.get(f'view=island&islandId={islandId}')
        bg_data = _extract_background_data(html, f'island {islandId}')
        return Island(self, bg_data)

    async def getCity(self, cityId: int) -> City:
        """Fetch and return full :class:`City` data for ``cityId``."""
        html = await self.get(f'view=city&cityId={cityId}')
        bg_data = _extract_background_data(html, f'city {cityId}')
        return City(self, bg_data)

    async def getPlayerHighScoreView(
        self,
        scoreType: str = HighScoreTypes.totalScore,
        offset: Optional[int] = None,
        showMe: bool = True,
        searchUser: str = '',
        searchOnlyFriends: bool = False,
        searchOnlyAllies: bool = False,
    ) -> 'PlayerHighScoreView':
        """Fetch the player highscore view for the requested category, offset, or filter."""
        params: Dict[str, str] = {
            'view': 'highscore',
            'highscoreType': scoreType,
        }
        if offset is not None:
            params['offset'] = str(offset)
        elif showMe and not searchUser:
            params['showMe'] = '1'
        if searchUser:
            params['searchUser'] = searchUser
        if searchOnlyFriends:
            params['searchOnlyFriends'] = '1'
        if searchOnlyAllies:
            params['searchOnlyAllies'] = '1'

        resp = await self.get_ajax(params=params)
        if resp.view_html is None:
            raise ValueError('Missing view HTML in player highscore response')
        return PlayerHighScoreView(self, resp.view_html)

    async def getAllianceHighScoreView(
        self,
        scoreType: str = AllianceHighScoreTypes.totalScore,
        offset: Optional[int] = None,
        searchAlliance: str = '',
        searchAllianceTag: str = '',
    ) -> 'AllianceHighScoreView':
        """Fetch the alliance highscore view (``view=highscoreAlly``)."""
        params: Dict[str, str] = {
            'view': 'highscoreAlly',
            'activeTab': 'tab_highscoreAlly',
            'highscoreType': scoreType,
        }
        if offset is not None:
            params['offset'] = str(offset)
        if searchAlliance:
            params['searchAlliance'] = searchAlliance
        if searchAllianceTag:
            params['searchAllianceTag'] = searchAllianceTag

        resp = await self.get_ajax(params=params)
        if resp.view_html is None:
            raise ValueError('Missing view HTML in alliance highscore response')
        return AllianceHighScoreView(self, resp.view_html)

    @property
    def isMayorActive(self) -> bool:
        """Whether the Mayor advisor icon currently shows an active/new event highlight."""
        return 'active' in (self.mayorStatus or '')

    @property
    def isMilitaryActive(self) -> bool:
        """Whether the Military advisor icon currently shows an active highlight."""
        return 'active' in (self.militaryStatus or '')

    @property
    def isMilitaryAlert(self) -> bool:
        """Whether the Military advisor icon currently indicates an incoming attack alert."""
        return 'alert' in (self.militaryStatus or '')

    @property
    def isResearchActive(self) -> bool:
        """Whether the Research advisor icon indicates an available research."""
        return 'active' in (self.researchStatus or '')

    @property
    def isDiplomacyActive(self) -> bool:
        """Whether the Diplomacy advisor icon indicates unread diplomatic messages."""
        return 'active' in (self.diplomacyStatus or '')

    async def getMayorView(self, offset: int = 0) -> MayorView:
        """Fetch the mayor / trade advisor message view starting at ``offset``."""
        resp = await self.get_ajax(params={'view': 'tradeAdvisor', 'offset': str(offset)})
        if resp.view_html is None:
            raise ValueError('Missing view HTML in mayor advisor response')
        return MayorView(self, resp)

    async def getTradeRoutesView(self, page: int = 0) -> TradeRoutesView:
        """Fetch the Mayor Trade Routes view (``view=tradeRoutes``, read-only)."""
        params: Dict[str, str] = {'view': 'tradeRoutes', 'activeTab': 'tab_tradeRoutes'}
        if page:
            params['page'] = str(page)
        resp = await self.get_ajax(params=params)
        if resp.view_html is None:
            raise ValueError('Missing view HTML in trade routes response')
        return TradeRoutesView(self, resp)

    async def getMilitaryView(self) -> MilitaryView:
        """Fetch the military advisor view containing movements, combats, and occupations."""
        resp = await self.get_ajax(params={'view': 'militaryAdvisor'})
        movements = resp.view_script_params.get('militaryAndFleetMovements') or []
        return MilitaryView(
            self,
            movements,
            resp.template_data,
            viewData=resp,
            viewScriptParams=resp.view_script_params,
        )

    async def getCombatReportsView(self, offset: int = 0) -> CombatReportsView:
        """Fetch the Military Advisor Combat Reports tab (read-only)."""
        params: Dict[str, str] = {
            'view': 'militaryAdvisorCombatList',
            'activeTab': 'tab_militaryAdvisorCombatList',
        }
        if offset:
            params['offset'] = str(offset)
        resp = await self.get_ajax(params=params)
        if resp.view_html is None:
            raise ValueError('Missing view HTML in combat reports response')
        return CombatReportsView(self, resp)

    async def getWarsView(self) -> WarsView:
        """Fetch the Military Advisor Gauntlet Wars tab (read-only)."""
        resp = await self.get_ajax(
            params={
                'view': 'militaryAdvisorWarList',
                'activeTab': 'tab_militaryAdvisorWarList',
            }
        )
        if resp.view_html is None:
            raise ValueError('Missing view HTML in gauntlet wars response')
        return WarsView(self, resp)

    async def getResearchView(
        self,
        researchType: Optional[str] = None,
        researchId: Optional[int] = None,
    ) -> ResearchView:
        """Fetch the Research Advisor view (read-only)."""
        params: Dict[str, str] = {'view': 'researchAdvisor'}
        if researchType:
            params['researchType'] = researchType
        if researchId is not None:
            params['researchId'] = str(researchId)
        resp = await self.get_ajax(params=params)
        if resp.view_html is None:
            raise ValueError('Missing view HTML in research advisor response')
        return ResearchView(self, resp)

    async def getDiplomacyView(
        self,
        box: str = 'inbox',
        offset: int = 0,
    ) -> DiplomacyView:
        """Fetch a Diplomacy Advisor mailbox view (``inbox``, ``outbox``, ``archiveInbox``, ``archiveOutbox``)."""
        view_name = DiplomacyView._BOX_TO_VIEW.get(box)
        if view_name is None:
            raise ValueError(f'Unknown diplomacy mailbox {box!r}')
        params: Dict[str, str] = {'view': view_name}
        if view_name == 'diplomacyAdvisor':
            params['activeTab'] = 'tab_diplomacyAdvisor'
        if offset:
            params['offset'] = str(offset)
        resp = await self.get_ajax(params=params)
        if resp.view_html is None:
            raise ValueError('Missing view HTML in diplomacy advisor response')
        return DiplomacyView(self, resp, mailboxType=box)

    async def getDiplomacyAgoraView(
        self,
        islandId: Optional[int] = None,
    ) -> DiplomacyAgoraView:
        """Fetch the Diplomacy Advisor Agora tab (read-only)."""
        params: Dict[str, str] = {
            'view': 'diplomacyIslandBoard',
            'activeTab': 'tab_diplomacyIslandBoard',
        }
        if islandId is not None:
            params['islandId'] = str(islandId)
        resp = await self.get_ajax(params=params)
        if resp.view_html is None:
            raise ValueError('Missing view HTML in diplomacy agora response')
        return DiplomacyAgoraView(self, resp)

    async def getDiplomacyTreatiesView(self) -> DiplomacyTreatiesView:
        """Fetch the Diplomacy Advisor Treaties tab (read-only)."""
        resp = await self.get_ajax(
            params={'view': 'diplomacyTreaty', 'activeTab': 'tab_diplomacyTreaty'}
        )
        if resp.view_html is None:
            raise ValueError('Missing view HTML in diplomacy treaties response')
        return DiplomacyTreatiesView(self, resp)

    async def getDiplomacyAllianceView(self) -> DiplomacyAllianceView:
        """Fetch the Diplomacy Advisor Alliance tab (read-only)."""
        resp = await self.get_ajax(
            params={'view': 'diplomacyAlly', 'activeTab': 'tab_diplomacyAlly'}
        )
        if resp.view_html is None:
            raise ValueError('Missing view HTML in diplomacy alliance response')
        return DiplomacyAllianceView(self, resp)

    async def getDiplomacyAllianceInfoView(self) -> DiplomacyAllianceInfoView:
        """Fetch the Diplomacy Advisor Alliance Information sub-view (read-only)."""
        resp = await self.get_ajax(params={'view': 'diplomacyAllyInfo'})
        if resp.view_html is None:
            raise ValueError('Missing view HTML in alliance info response')
        return DiplomacyAllianceInfoView(self, resp)

    async def getDiplomacyAllianceMembersView(self) -> DiplomacyAllianceMembersView:
        """Fetch the Diplomacy Advisor Alliance Member List sub-view (read-only)."""
        resp = await self.get_ajax(params={'view': 'diplomacyAllyMemberlist'})
        if resp.view_html is None:
            raise ValueError('Missing view HTML in alliance member list response')
        return DiplomacyAllianceMembersView(self, resp)

    async def getIgnoredPlayers(self) -> List[Dict[str, Any]]:
        """Fetch the Diplomacy Advisor Ignored Players tab (read-only)."""
        resp = await self.get_ajax(
            params={'view': 'ignoreList', 'activeTab': 'tab_ignoreList'}
        )
        ignore_td = resp.template_data.get('ignoreList')
        if isinstance(ignore_td, list):
            return [item if isinstance(item, dict) else {'entry': item} for item in ignore_td]
        if resp.view_html:
            soup = make_soup(resp.view_html)
            entries: List[Dict[str, Any]] = []
            for a in soup.select("a[href*='deleteIgnoreList'], a[href*='unignore']"):
                entries.append(
                    {
                        'name': a.get_text(' ', strip=True),
                        'href': str(a.get('href') or ''),
                    }
                )
            return entries
        return []


class PlayerHighScoreTable(Table):
    """Parsed player highscore table rows."""

    playerHighScoreView: 'PlayerHighScoreView'
    rows: List[PlayerHighScoreTableRow]

    def __init__(
        self,
        playerHighScoreView: 'PlayerHighScoreView',
        rangeStart: Optional[int],
        tableHTML: Union[str, Tag],
    ) -> None:
        """Parse player highscore rows from the supplied HTML table or tag."""
        self.playerHighScoreView = playerHighScoreView
        super().__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            if len(row._cells) < 4:
                continue
            cells = row._cells
            position = parse_int(cells[0].text)

            i_tag = cells[1].tag.find('i')
            title_text = i_tag.get_text(strip=True) if i_tag is not None else ''
            playerTitle = title_text if title_text else None

            playerFlagTag = _extract_flag_tag(cells[1].tag)

            player_a = cells[1].tag.find('a')
            name_span = cells[1].tag.find('span', class_='avatarName')
            if name_span is not None:
                playerName = name_span.get_text(strip=True)
            elif player_a is not None:
                direct_name = ''.join(
                    str(t) for t in player_a.find_all(string=True, recursive=False)
                ).strip()
                playerName = (
                    direct_name
                    or str(player_a.get('title', '')).strip()
                    or cells[1].text
                )
            else:
                playerName = cells[1].text

            playerId = (
                (parse_query_int(player_a.get('href'), 'avatarId') or 0)
                if player_a is not None
                else 0
            )
            isAlly = 'ownally' in row.classes
            isBanned = 'banned' in row.classes or cells[1].tag.find(class_='banned') is not None
            has_vac_icon = cells[1].tag.find('img', src=_VACATION_ICON_RE) is not None
            has_div_img = cells[1].tag.select_one('div > img') is not None
            isVacation = has_vac_icon or (not isBanned and has_div_img)

            a_classes = list(player_a.get('class') or []) if player_a is not None else []
            isInactive = ('gray' in cells[3].classes) or ('gray' in a_classes)

            ally_a = cells[2].tag.find('a')
            if ally_a is not None:
                ally_text = ally_a.get_text(strip=True)
                playerAllianceTag = ally_text if ally_text else None
                playerAllianceId = parse_query_int(ally_a.get('href'), 'allyId')
            else:
                playerAllianceTag = None
                playerAllianceId = None

            points = parse_int(cells[3].title or cells[3].text) or 0

            self.rows.append(
                PlayerHighScoreTableRow(
                    position,
                    playerTitle,
                    playerFlagTag,
                    playerName,
                    playerId,
                    isAlly,
                    isVacation,
                    isInactive,
                    isBanned,
                    playerAllianceTag,
                    playerAllianceId,
                    points,
                )
            )


class PlayerHighScoreView:
    """Player highscore view with pagination, score-type switching, and search."""

    client: Client
    playerHighScoreTable: PlayerHighScoreTable
    availableRanges: List[Tuple[int, int]]
    currentScoreType: str
    currentRangeStart: int
    currentRangeEnd: int

    def __init__(self, client: Client, viewData: str) -> None:
        """Parse player highscore controls and table from ``changeView`` HTML."""
        self.client = client
        self.__player_high_score_view_data = viewData
        self.availableRanges = []

        soup = make_soup(viewData)
        (
            self.currentScoreType,
            self.availableRanges,
            self._selectedOffset,
        ) = _parse_highscore_selects(soup)

        table_tag = soup.find('table', class_='table01') or soup.find('table')
        table = PlayerHighScoreTable(
            self,
            self._selectedOffset,
            table_tag if table_tag is not None else viewData,
        )
        self.playerHighScoreTable = table
        self.currentRangeStart, self.currentRangeEnd = _compute_range_bounds(
            table.rows,
            self._selectedOffset,
        )

    async def getNextPage(self) -> 'PlayerHighScoreView':
        """Fetch the next page of player highscore results."""
        next_offset = self.currentRangeEnd if self.currentRangeEnd > 0 else 0
        if self.availableRanges:
            max_offset = max(0, self.availableRanges[-1][0] - 1)
            next_offset = min(next_offset, max_offset)
        return await self.client.getPlayerHighScoreView(
            scoreType=self.currentScoreType,
            offset=next_offset,
            showMe=False,
        )

    async def getPreviousPage(self) -> 'PlayerHighScoreView':
        """Fetch the previous page of player highscore results."""
        prev_offset = max(0, (self.currentRangeStart - 1) - 50) if self.currentRangeStart > 0 else 0
        return await self.client.getPlayerHighScoreView(
            scoreType=self.currentScoreType,
            offset=prev_offset,
            showMe=False,
        )

    async def getFirstPage(self) -> 'PlayerHighScoreView':
        """Fetch the first page of player highscore results."""
        offset = max(0, self.availableRanges[0][0] - 1) if self.availableRanges else 0
        return await self.client.getPlayerHighScoreView(
            scoreType=self.currentScoreType,
            offset=offset,
            showMe=False,
        )

    async def getLastPage(self) -> 'PlayerHighScoreView':
        """Fetch the last page of player highscore results."""
        offset = max(0, self.availableRanges[-1][0] - 1) if self.availableRanges else 0
        return await self.client.getPlayerHighScoreView(
            scoreType=self.currentScoreType,
            offset=offset,
            showMe=False,
        )

    async def setScoreType(self, scoreType: str) -> 'PlayerHighScoreView':
        """Switch highscore category using a value from :class:`HighScoreTypes`."""
        return await self.client.getPlayerHighScoreView(
            scoreType=scoreType,
            offset=self._selectedOffset,
            showMe=(self._selectedOffset is None),
        )

    @overload
    async def getRange(self, range: Tuple[int, int]) -> 'PlayerHighScoreView':
        ...

    @overload
    async def getRange(self, start: int, end: int) -> 'PlayerHighScoreView':
        ...

    async def getRange(self, *args: Any, **kwargs: Any) -> 'PlayerHighScoreView':
        """Fetch player highscore results starting at the given ``(start, end)`` range."""
        offset = _extract_range_offset(*args, **kwargs)
        return await self.client.getPlayerHighScoreView(
            scoreType=self.currentScoreType,
            offset=offset,
            showMe=False,
        )

    async def searchByUsername(
        self,
        username: str,
        searchOnlyFriends: bool = False,
        searchOnlyAllies: bool = False,
    ) -> 'PlayerHighScoreView':
        """Search player highscores by username, optionally filtering to friends or allies."""
        return await self.client.getPlayerHighScoreView(
            scoreType=self.currentScoreType,
            showMe=False,
            searchUser=username,
            searchOnlyFriends=searchOnlyFriends,
            searchOnlyAllies=searchOnlyAllies,
        )


class AllianceHighScoreTable(Table):
    """Parsed alliance highscore table rows."""

    allianceHighScoreView: 'AllianceHighScoreView'
    rows: List[AllianceHighScoreTableRow]

    def __init__(
        self,
        allianceHighScoreView: 'AllianceHighScoreView',
        rangeStart: Optional[int],
        tableHTML: Union[str, Tag],
    ) -> None:
        """Parse alliance highscore rows from the supplied HTML table or tag."""
        self.allianceHighScoreView = allianceHighScoreView
        super().__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            if len(row._cells) < 5:
                continue
            cells = row._cells
            position = parse_int(cells[0].text)
            allianceFlagTag = _extract_flag_tag(cells[1].tag)

            name_span = cells[1].tag.find('span', class_='allyName')
            name_text = name_span.get_text(strip=True) if name_span is not None else ''
            allianceName = name_text if name_text else None

            ally_a = cells[1].tag.find('a', class_='allyLink') or cells[1].tag.find('a')
            allianceTag = ''
            if ally_a is not None:
                direct_text = ''.join(
                    str(node) for node in ally_a.find_all(string=True, recursive=False)
                ).strip()
                tag_match = re.search(r'\(([^()]+)\)\s*$', direct_text)
                if not tag_match:
                    tag_match = re.search(r'\(([^()]+)\)\s*$', ally_a.get_text(' ', strip=True))
                if tag_match:
                    allianceTag = tag_match.group(1).strip()

            allianceId = (
                (parse_query_int(ally_a.get('href'), 'allyId') or 0)
                if ally_a is not None
                else 0
            )
            isAlly = ('ownally' in row.classes) or ('own' in row.classes)
            members = parse_int(cells[2].text) or 0
            points = parse_int(cells[3].title or cells[3].text) or 0
            averagePoints = parse_int(cells[4].title or cells[4].text) or 0

            self.rows.append(
                AllianceHighScoreTableRow(
                    position,
                    allianceFlagTag,
                    allianceName,
                    allianceTag,
                    allianceId,
                    isAlly,
                    members,
                    points,
                    averagePoints,
                )
            )


class AllianceHighScoreView:
    """Alliance highscore view with pagination, score-type switching, and search."""

    client: Client
    allianceHighScoreTable: AllianceHighScoreTable
    availableRanges: List[Tuple[int, int]]
    currentScoreType: str
    currentRangeStart: int
    currentRangeEnd: int

    def __init__(self, client: Client, viewData: str) -> None:
        """Parse alliance highscore controls and table from ``changeView`` HTML."""
        self.client = client
        self.__alliance_high_score_view_data = viewData
        self.availableRanges = []

        soup = make_soup(viewData)
        (
            self.currentScoreType,
            self.availableRanges,
            self._selectedOffset,
        ) = _parse_highscore_selects(soup)

        table_tag = soup.find('table', class_='table01') or soup.find('table')
        table = AllianceHighScoreTable(
            self,
            self._selectedOffset,
            table_tag if table_tag is not None else viewData,
        )
        self.allianceHighScoreTable = table
        self.currentRangeStart, self.currentRangeEnd = _compute_range_bounds(
            table.rows,
            self._selectedOffset,
        )

    async def getNextPage(self) -> 'AllianceHighScoreView':
        """Fetch the next page of alliance highscore results."""
        next_offset = self.currentRangeEnd if self.currentRangeEnd > 0 else 0
        if self.availableRanges:
            max_offset = max(0, self.availableRanges[-1][0] - 1)
            next_offset = min(next_offset, max_offset)
        return await self.client.getAllianceHighScoreView(
            scoreType=self.currentScoreType,
            offset=next_offset,
        )

    async def getPreviousPage(self) -> 'AllianceHighScoreView':
        """Fetch the previous page of alliance highscore results."""
        prev_offset = max(0, (self.currentRangeStart - 1) - 50) if self.currentRangeStart > 0 else 0
        return await self.client.getAllianceHighScoreView(
            scoreType=self.currentScoreType,
            offset=prev_offset,
        )

    async def getFirstPage(self) -> 'AllianceHighScoreView':
        """Fetch the first page of alliance highscore results."""
        offset = max(0, self.availableRanges[0][0] - 1) if self.availableRanges else 0
        return await self.client.getAllianceHighScoreView(
            scoreType=self.currentScoreType,
            offset=offset,
        )

    async def getLastPage(self) -> 'AllianceHighScoreView':
        """Fetch the last page of alliance highscore results."""
        offset = max(0, self.availableRanges[-1][0] - 1) if self.availableRanges else 0
        return await self.client.getAllianceHighScoreView(
            scoreType=self.currentScoreType,
            offset=offset,
        )

    async def setScoreType(self, scoreType: str) -> 'AllianceHighScoreView':
        """Switch alliance highscore category using :class:`AllianceHighScoreTypes`."""
        return await self.client.getAllianceHighScoreView(
            scoreType=scoreType,
            offset=self._selectedOffset,
        )

    @overload
    async def getRange(self, range: Tuple[int, int]) -> 'AllianceHighScoreView':
        ...

    @overload
    async def getRange(self, start: int, end: int) -> 'AllianceHighScoreView':
        ...

    async def getRange(self, *args: Any, **kwargs: Any) -> 'AllianceHighScoreView':
        """Fetch alliance highscore results starting at the given ``(start, end)`` range."""
        offset = _extract_range_offset(*args, **kwargs)
        return await self.client.getAllianceHighScoreView(
            scoreType=self.currentScoreType,
            offset=offset,
        )

    async def searchByAllianceName(self, name: str) -> 'AllianceHighScoreView':
        """Search alliance highscores by alliance name."""
        return await self.client.getAllianceHighScoreView(
            scoreType=self.currentScoreType,
            searchAlliance=name,
        )

    async def searchByAllianceTag(self, tag: str) -> 'AllianceHighScoreView':
        """Search alliance highscores by alliance tag."""
        return await self.client.getAllianceHighScoreView(
            scoreType=self.currentScoreType,
            searchAllianceTag=tag,
        )

