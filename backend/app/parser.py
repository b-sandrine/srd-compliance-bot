from __future__ import annotations
import os
import re
from typing import List, Optional, Tuple
import httpx
from notion_client import AsyncClient as NotionClient

from .models import SRDField, FieldType


# ---------------------------------------------------------------------------
# Notion helpers
# ---------------------------------------------------------------------------

def _get_notion_client() -> NotionClient:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise ValueError("NOTION_TOKEN env var is not set. Add it to backend/.env")
    return NotionClient(auth=token)


def _extract_notion_page_id(url: str) -> str:
    """Pull the 32-char hex page ID out of any Notion URL format."""
    # Strip query string & fragment
    clean = re.split(r"[?#]", url)[0]
    # UUID with dashes
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", clean, re.I)
    if m:
        return m.group(1)
    # 32 hex chars (no dashes)
    m = re.search(r"([0-9a-f]{32})", clean, re.I)
    if m:
        raw = m.group(1)
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    raise ValueError(f"Cannot extract a Notion page ID from: {url}")


def _rich_text(cell: list) -> str:
    return "".join(rt.get("plain_text", "") for rt in cell).strip()


# ---------------------------------------------------------------------------
# Type / required inference
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "text": FieldType.TEXT, "string": FieldType.TEXT, "short text": FieldType.TEXT,
    "number": FieldType.NUMBER, "integer": FieldType.NUMBER, "numeric": FieldType.NUMBER,
    "date": FieldType.DATE, "datetime": FieldType.DATE,
    "dropdown": FieldType.DROPDOWN, "select": FieldType.DROPDOWN, "list": FieldType.DROPDOWN,
    "multiselect": FieldType.MULTISELECT, "multi-select": FieldType.MULTISELECT,
    "multi select": FieldType.MULTISELECT,
    "file": FieldType.FILE, "upload": FieldType.FILE, "attachment": FieldType.FILE,
    "checkbox": FieldType.CHECKBOX, "boolean": FieldType.CHECKBOX, "check": FieldType.CHECKBOX,
    "radio": FieldType.RADIO,
    "textarea": FieldType.TEXTAREA, "long text": FieldType.TEXTAREA, "paragraph": FieldType.TEXTAREA,
    "email": FieldType.EMAIL,
    "phone": FieldType.PHONE, "tel": FieldType.PHONE, "telephone": FieldType.PHONE,
}


def _infer_type(raw: str) -> FieldType:
    low = raw.lower().strip()
    for key, val in _TYPE_MAP.items():
        if key in low:
            return val
    return FieldType.UNKNOWN


def _infer_required(raw: str) -> Optional[bool]:
    low = raw.lower().strip()
    if low in ("yes", "true", "required", "mandatory", "y", "1", "✓", "✔"):
        return True
    if low in ("no", "false", "optional", "n", "0", "–", "-", ""):
        return False
    return None


# ---------------------------------------------------------------------------
# Column-header mapping (shared by both Notion + Markdown parsers)
# ---------------------------------------------------------------------------

_COL_KEYWORDS = {
    "name":            ["field name", "field", "component", "name", "key"],
    "label":           ["label", "display name", "display", "title"],
    "type":            ["type", "field type", "data type", "input type"],
    "required":        ["required", "mandatory", "obligatory"],
    "hide_expression": ["hide", "condition", "expression", "visibility", "hide expression",
                        "show when", "visible when"],
    "validation":      ["validation", "rule", "constraint"],
    "options":         ["option", "value", "choice", "enum"],
    "notes":           ["note", "description", "remark", "comment"],
}


def _build_col_map(headers: List[str]) -> dict:
    col_map: dict = {}
    for idx, col in enumerate(headers):
        low = col.lower().strip()
        for key, keywords in _COL_KEYWORDS.items():
            if key not in col_map and any(kw in low for kw in keywords):
                col_map[key] = idx
    return col_map


def _row_to_field(cells: List[str], col_map: dict) -> Optional[SRDField]:
    def get(key: str) -> str:
        idx = col_map.get(key)
        if idx is not None and idx < len(cells):
            return cells[idx].strip()
        # fallback: first cell = name
        if key == "name" and cells:
            return cells[0].strip()
        return ""

    name = get("name")
    if not name:
        return None

    options_raw = get("options")
    options = [o.strip() for o in re.split(r"[,;|\n]", options_raw) if o.strip()] if options_raw else []

    validation_raw = get("validation")
    validation_rules = [v.strip() for v in re.split(r"[,;\n]", validation_raw) if v.strip()] if validation_raw else []

    hide_expr = get("hide_expression") or None

    return SRDField(
        name=name,
        label=get("label") or name,
        field_type=_infer_type(get("type")),
        required=_infer_required(get("required")),
        hide_expression=hide_expr,
        validation_rules=validation_rules,
        options=options,
        notes=get("notes") or None,
    )


# ---------------------------------------------------------------------------
# Notion page parser
# ---------------------------------------------------------------------------

async def _parse_notion_table(notion: NotionClient, table_block: dict) -> List[SRDField]:
    has_header = table_block["table"].get("has_column_header", True)
    rows_resp = await notion.blocks.children.list(block_id=table_block["id"])
    rows = rows_resp["results"]
    if not rows:
        return []

    parsed_rows = [[_rich_text(cell) for cell in row["table_row"]["cells"]] for row in rows]

    if has_header and len(parsed_rows) > 1:
        headers = parsed_rows[0]
        data = parsed_rows[1:]
    else:
        headers = []
        data = parsed_rows

    col_map = _build_col_map(headers)
    return [f for row in data if (f := _row_to_field(row, col_map))]


async def _blocks_to_fields(notion: NotionClient, blocks: list) -> List[SRDField]:
    fields: List[SRDField] = []
    for block in blocks:
        btype = block["type"]
        if btype == "table":
            fields.extend(await _parse_notion_table(notion, block))
        elif btype in ("child_page", "child_database"):
            child_resp = await notion.blocks.children.list(block_id=block["id"])
            fields.extend(await _blocks_to_fields(notion, child_resp["results"]))
    return fields


async def _parse_notion_page(page_id: str) -> List[SRDField]:
    notion = _get_notion_client()
    resp = await notion.blocks.children.list(block_id=page_id)
    return await _blocks_to_fields(notion, resp["results"])


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def _parse_markdown_tables(content: str) -> List[Tuple[List[str], List[List[str]]]]:
    """Extract (headers, rows) tuples from raw markdown table syntax."""
    tables = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and line.endswith("|"):
            block: List[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            if len(block) < 2:
                continue
            headers = [c.strip() for c in block[0].split("|")[1:-1]]
            data_rows: List[List[str]] = []
            for row_line in block[2:]:  # skip separator (index 1)
                row = [c.strip() for c in row_line.split("|")[1:-1]]
                if any(row):
                    data_rows.append(row)
            tables.append((headers, data_rows))
        else:
            i += 1
    return tables


async def parse_markdown(content: str) -> List[SRDField]:
    fields: List[SRDField] = []
    for headers, rows in _parse_markdown_tables(content):
        col_map = _build_col_map(headers)
        for row in rows:
            f = _row_to_field(row, col_map)
            if f:
                fields.append(f)
    return fields


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def parse_srd_url(url: str) -> List[SRDField]:
    if "notion.so" in url or "notion.com" in url:
        page_id = _extract_notion_page_id(url)
        return await _parse_notion_page(page_id)

    # Generic URL — fetch and treat as Markdown
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return await parse_markdown(resp.text)
