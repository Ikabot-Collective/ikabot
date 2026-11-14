"""Shared HTML, JSON, and Ikariam payload parsing helpers."""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag


def parse_int(value: Any) -> Optional[int]:
    """Parse an integer from raw numeric or localized Ikariam string values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    # Strip localized thousands separators, spaces, non-breaking spaces, and leading '+'
    cleaned = re.sub(r"[\s.,\xa0\u202f+]", "", text)
    if not re.fullmatch(r"-?\d+", cleaned):
        return None
    return int(cleaned)


def parse_float(value: Any) -> Optional[float]:
    """Parse a float from raw numeric or localized Ikariam string values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    cleaned = re.sub(r"[%\s\xa0\u202f+]", "", text)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(".") > cleaned.rfind(","):
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        after_last_comma = cleaned.rsplit(",", 1)[-1]
        if len(after_last_comma) == 3 and after_last_comma.isdigit():
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    return float(cleaned)


def decode_unicode_escape(text: Optional[str]) -> str:
    """Decode literal ``\\uXXXX`` escape sequences if present in an Ikariam string."""
    if not text:
        return ""
    return re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda match: chr(int(match.group(1), 16)),
        text,
    )


def unescape_js_single_quoted(raw: str) -> str:
    """Unescape a JavaScript single-quoted string literal into plain text."""
    out: List[str] = []
    i = 0
    length = len(raw)
    while i < length:
        ch = raw[i]
        if ch == "\\" and i + 1 < length:
            nxt = raw[i + 1]
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            if nxt in ("'", '"', "/"):
                out.append(nxt)
                i += 2
                continue
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "r":
                out.append("\r")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def extract_js_single_quoted_arg(text: str, marker_pattern: str) -> Optional[str]:
    """Extract the unescaped contents of a JS single-quoted string after ``marker_pattern``."""
    match = re.search(marker_pattern, text)
    if not match:
        return None
    i = match.end()
    length = len(text)
    chars: List[str] = []
    while i < length:
        ch = text[i]
        if ch == "\\" and i + 1 < length:
            chars.append(ch)
            chars.append(text[i + 1])
            i += 2
            continue
        if ch == "'":
            return unescape_js_single_quoted("".join(chars))
        chars.append(ch)
        i += 1
    return None


def extract_js_json_parse(text: str, key: str) -> Optional[Any]:
    """Extract and decode ``<key>[:=] JSON.parse('...')`` from JavaScript source."""
    raw = extract_js_single_quoted_arg(text, rf"\b{re.escape(key)}\s*[:=]\s*JSON\.parse\('")
    if raw is None:
        return None
    return json.loads(raw, strict=False)


def extract_js_json_string(text: str, key: str) -> Optional[Any]:
    """Extract and decode ``<key>[:=] '{...}'`` from JavaScript source."""
    raw = extract_js_single_quoted_arg(text, rf"\b{re.escape(key)}\s*[:=]\s*'")
    if raw is None:
        return None
    return json.loads(raw, strict=False)


def extract_js_object(text: str, var_name: str) -> Optional[str]:
    """Extract a brace-balanced JS object literal following ``var_name =``."""
    match = re.search(rf"\b{re.escape(var_name)}\s*=\s*\{{", text)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    in_quote: Optional[str] = None
    i = start
    length = len(text)
    while i < length:
        ch = text[i]
        if in_quote:
            if ch == "\\" and i + 1 < length:
                i += 2
                continue
            if ch == in_quote:
                in_quote = None
        else:
            if ch in ("'", '"'):
                in_quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        i += 1
    return None


def extract_ajax_responder(html: str) -> list:
    """Extract the ``ajax.Responder`` command list embedded in a full Ikariam HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    decoder = json.JSONDecoder(strict=False)
    for script in soup.find_all("script"):
        content = script.string or script.get_text() or ""
        idx = content.find("ajax.Responder")
        if idx == -1:
            continue
        arr_start = content.find("[[", idx)
        if arr_start == -1:
            continue
        commands, _ = decoder.raw_decode(content, arr_start)
        return commands
    raise ValueError("Could not find ajax.Responder payload in HTML response")


def parse_query_params(
    url: Optional[str],
    *,
    normalize_action_request: bool = False,
) -> Dict[str, str]:
    """Parse all query string parameters from a URL or query fragment into a dict."""
    if not url:
        return {}
    parsed = urlparse(url)
    query = parsed.query if parsed.query else url.lstrip("?")
    if "=" not in query:
        return {}
    raw_params = parse_qs(query, keep_blank_values=True)
    result = {key: vals[-1] for key, vals in raw_params.items() if vals}
    if normalize_action_request and "actionRequest" in result:
        result["actionRequest"] = "REQUESTID"
    return result


def parse_query_str(url: Optional[str], param: str) -> Optional[str]:
    """Extract a query parameter string value from a URL or query fragment."""
    if not url:
        return None
    parsed = urlparse(url)
    query = parsed.query if parsed.query else url.lstrip("?")
    values = parse_qs(query).get(param)
    return values[0] if values else None


def parse_query_int(url: Optional[str], param: str) -> Optional[int]:
    """Extract an integer query parameter from a URL or query fragment."""
    return parse_int(parse_query_str(url, param))


def format_feedback(feedback: list) -> str:
    """Format Ikariam ``provideFeedback`` entries into a readable message string."""
    return "; ".join(
        str(item.get("text", "")).strip()
        for item in feedback
        if isinstance(item, dict) and item.get("text")
    )


def has_feedback_error(feedback: list) -> bool:
    """Return whether ``provideFeedback`` contains an error-type entry (``type == 11``)."""
    return any(isinstance(item, dict) and item.get("type") == 11 for item in feedback)


def make_soup(html: str) -> BeautifulSoup:
    """Create a BeautifulSoup tree using Python's built-in HTML parser."""
    return BeautifulSoup(html, "html.parser")


@dataclass
class AjaxResponse:
    """Structured view of Ikariam's ``ajax=1`` JSON command array."""

    commands: list = field(default_factory=list)
    global_data: Optional[Dict[str, Any]] = None
    background_data: Optional[Dict[str, Any]] = None
    view_name: Optional[str] = None
    view_html: Optional[str] = None
    view_script_params: Dict[str, Any] = field(default_factory=dict)
    template_data: Dict[str, Any] = field(default_factory=dict)
    feedback: list = field(default_factory=list)
    reload_link: Optional[str] = None
    closed_views: List[str] = field(default_factory=list)

    def get_window_html(self, window_name: Optional[str] = None) -> Optional[str]:
        """Return the HTML body of an ``addWindow`` command matching ``window_name``."""
        for item in self.commands:
            if not isinstance(item, list) or len(item) < 2 or item[0] != "addWindow":
                continue
            payload = item[1]
            if isinstance(payload, list) and len(payload) >= 2:
                name, body = payload[0], payload[1]
                if (window_name is None or name == window_name) and isinstance(body, str):
                    return body
        return None


def parse_ajax_response(raw: Union[str, list]) -> AjaxResponse:
    """Parse an Ikariam ``ajax=1`` JSON payload into an :class:`AjaxResponse`."""
    commands = json.loads(raw, strict=False) if isinstance(raw, str) else raw
    parsed = AjaxResponse(commands=commands)
    for item in commands:
        if not isinstance(item, list) or len(item) < 2:
            continue
        cmd, payload = item[0], item[1]
        if cmd == "updateGlobalData" and isinstance(payload, dict):
            parsed.global_data = payload
            bg = payload.get("backgroundData")
            if isinstance(bg, dict) and bg:
                parsed.background_data = bg
        elif cmd == "updateBackgroundData" and isinstance(payload, dict):
            parsed.background_data = payload
        elif cmd == "changeView" and isinstance(payload, list):
            parsed.view_name = payload[0] if len(payload) > 0 else None
            parsed.view_html = payload[1] if len(payload) > 1 else None
            if len(payload) > 2 and isinstance(payload[2], dict):
                script_params = payload[2].get("viewScriptParams")
                if isinstance(script_params, dict):
                    parsed.view_script_params = script_params
        elif cmd == "updateTemplateData" and isinstance(payload, dict):
            parsed.template_data = payload
        elif cmd == "provideFeedback" and isinstance(payload, list):
            parsed.feedback = payload
        elif cmd == "closeView" and isinstance(payload, str):
            parsed.closed_views.append(payload)
        elif cmd == "custom" and isinstance(payload, list) and len(payload) >= 2:
            if payload[0] == "reload" and isinstance(payload[1], dict):
                parsed.reload_link = payload[1].get("link")
    return parsed


class TableCell:
    """Represents a ``<td>`` cell inside an HTML :class:`Table`."""

    tag: Tag
    classes: List[str]
    _class: str
    _content: str
    text: str
    title: Optional[str]

    def __init__(self, cell_tag: Tag) -> None:
        self.tag = cell_tag
        self.classes = list(cell_tag.get("class") or [])
        self._class = " ".join(self.classes)
        self._content = cell_tag.decode_contents()
        self.text = cell_tag.get_text(" ", strip=True)
        title = cell_tag.get("title")
        self.title = str(title) if title is not None else None


class TableRow:
    """Represents a ``<tr>`` row inside an HTML :class:`Table`."""

    tag: Tag
    classes: List[str]
    _class: str
    _cells: List[TableCell]

    def __init__(self, row_tag: Tag) -> None:
        self.tag = row_tag
        self.classes = list(row_tag.get("class") or [])
        self._class = " ".join(self.classes)
        self._cells = [
            TableCell(td) for td in row_tag.find_all("td", recursive=False)
        ]


class Table:
    """Base HTML table parser built on BeautifulSoup."""

    tag: Optional[Tag]
    _rows: List[TableRow]

    def __init__(self, tableHTML: Union[str, Tag]) -> None:
        if isinstance(tableHTML, Tag):
            table_tag = tableHTML if tableHTML.name == "table" else tableHTML.find("table")
        else:
            soup = make_soup(tableHTML)
            table_tag = soup.find("table")
        self.tag = table_tag
        self._rows = []
        if table_tag is None:
            return
        container = table_tag.find("tbody", recursive=False) or table_tag
        for tr in container.find_all("tr", recursive=False):
            row = TableRow(tr)
            if row._cells:
                self._rows.append(row)
