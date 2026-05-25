from __future__ import annotations
import os
import re
from typing import List, Optional, Tuple, Dict, Any
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
    clean = re.split(r"[?#]", url)[0]
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", clean, re.I)
    if m:
        return m.group(1)
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
    # Standard
    "text input": FieldType.TEXT,
    "text area": FieldType.TEXTAREA,
    "textarea": FieldType.TEXTAREA,
    "long text": FieldType.TEXTAREA,
    "paragraph": FieldType.TEXTAREA,
    "text": FieldType.TEXT,
    "string": FieldType.TEXT,
    "short text": FieldType.TEXT,
    "number input": FieldType.NUMBER,
    "number": FieldType.NUMBER,
    "integer": FieldType.NUMBER,
    "numeric": FieldType.NUMBER,
    "date picker": FieldType.DATE,
    "date": FieldType.DATE,
    "datetime": FieldType.DATE,
    "time picker": FieldType.DATE,
    "dropdown": FieldType.DROPDOWN,
    "select": FieldType.DROPDOWN,
    "list": FieldType.DROPDOWN,
    "location widget": FieldType.DROPDOWN,
    "country widget": FieldType.DROPDOWN,
    "multiselect": FieldType.MULTISELECT,
    "multi-select": FieldType.MULTISELECT,
    "multi select": FieldType.MULTISELECT,
    "file upload": FieldType.FILE,
    "file": FieldType.FILE,
    "upload": FieldType.FILE,
    "attachment": FieldType.FILE,
    "checkbox": FieldType.CHECKBOX,
    "boolean": FieldType.CHECKBOX,
    "check": FieldType.CHECKBOX,
    "radio button": FieldType.RADIO,
    "radio": FieldType.RADIO,
    "email": FieldType.EMAIL,
    "intl. phone number": FieldType.PHONE,
    "intl phone number": FieldType.PHONE,
    "phone": FieldType.PHONE,
    "tel": FieldType.PHONE,
    "telephone": FieldType.PHONE,
    # IremboGov-specific widget types
    "tin fetch": FieldType.TEXT,
    "tin": FieldType.TEXT,
    "id fetch": FieldType.TEXT,
    "nid fetch": FieldType.TEXT,
}


def _infer_type(raw: str) -> FieldType:
    low = raw.lower().strip()
    # Longest-match first to avoid "text" matching "text input" incorrectly
    for key in sorted(_TYPE_MAP.keys(), key=len, reverse=True):
        if key in low:
            return _TYPE_MAP[key]
    return FieldType.UNKNOWN


def _infer_required(raw: str) -> Optional[bool]:
    low = raw.lower().strip()
    if low in ("yes", "true", "required", "mandatory", "y", "1", "✓", "✔"):
        return True
    if low in ("no", "false", "optional", "n", "0", "–", "-", ""):
        return False
    return None


def _required_from_validation(validation_raw: str) -> Optional[bool]:
    """Infer required status from validation rules column (e.g. '-Required', '-Optional')."""
    low = validation_raw.lower()
    if re.search(r"\brequired\b", low) and not re.search(r"\boptional\b", low):
        return True
    if re.search(r"\boptional\b", low):
        return False
    return None


def _extract_options(raw: str) -> List[str]:
    """Extract list values from a cell that may contain placeholder text + bullet list."""
    if not raw:
        return []

    options: List[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        # Match lines starting with - or • (bullet items)
        m = re.match(r'^[-•]\s*(.*)', stripped)
        if m:
            item = m.group(1).strip()
            # Strip markdown bold markers
            item = re.sub(r'\*\*([^*]+)\*\*', r'\1', item).strip()
            if item:
                options.append(item)

    # Fallback: comma/semicolon list after "values:" label
    if not options:
        m = re.search(r'(?:values?|options?|choices?)\s*[:\-]\s*(.+)', raw, re.IGNORECASE | re.DOTALL)
        if m:
            blob = m.group(1)
            options = [
                re.sub(r'\*\*([^*]+)\*\*', r'\1', v).strip()
                for v in re.split(r'[,;]', blob)
                if v.strip() and not v.strip().startswith('**')
            ]

    return [o for o in options if o]


def _clean_display_rule(raw: str) -> Optional[str]:
    """Return None if field is always visible, else return the display condition."""
    if not raw:
        return None
    low = raw.lower().strip()
    if low in ("", "always on display", "always displayed", "always visible", "n/a", "-"):
        return None
    return raw.strip()


# ---------------------------------------------------------------------------
# Column-header mapping
# ---------------------------------------------------------------------------

_COL_KEYWORDS: Dict[str, List[str]] = {
    "name":            ["field name", "field", "component", "name", "key"],
    "label":           ["label", "display name", "display", "title"],
    "type":            ["type", "field type", "data type", "input type"],
    "required":        ["required", "mandatory", "obligatory"],
    "hide_expression": ["hide", "condition", "expression", "visibility", "hide expression",
                        "show when", "visible when", "display rule", "display condition"],
    "validation":      ["validation", "rule", "constraint"],
    "options":         ["option", "value", "choice", "enum", "placeholder"],
    "notes":           ["note", "description", "remark", "comment", "tooltip", "widget"],
    "section":         ["section"],
    "block":           ["block"],
    "error":           ["error message", "error"],
}


def _build_col_map(headers: List[str]) -> dict:
    col_map: dict = {}
    for idx, col in enumerate(headers):
        low = col.lower().strip()
        for key, keywords in _COL_KEYWORDS.items():
            if key not in col_map and any(kw in low for kw in keywords):
                col_map[key] = idx
    return col_map


def _row_to_field(
    cells: List[str],
    col_map: dict,
    section_ctx: str = "",
    block_ctx: str = "",
) -> Optional[SRDField]:
    def get(key: str) -> str:
        idx = col_map.get(key)
        if idx is not None and idx < len(cells):
            return cells[idx].strip()
        if key == "name" and cells:
            return cells[0].strip()
        return ""

    name = get("name")
    if not name:
        return None

    # Skip header-like rows and separator rows
    if re.match(r'^[-:| ]+$', name):
        return None

    # --- options ---
    options_raw = get("options")
    options = _extract_options(options_raw)

    # --- validation + required ---
    validation_raw = get("validation")
    validation_rules = [v.strip() for v in re.split(r"[;\n]", validation_raw) if v.strip()] if validation_raw else []

    required_val = _infer_required(get("required"))
    if required_val is None and validation_raw:
        required_val = _required_from_validation(validation_raw)

    # --- hide expression from display rules ---
    hide_raw = get("hide_expression")
    hide_expr = _clean_display_rule(hide_raw)

    # --- section / block context (use cell value or carry-forward context) ---
    section = get("section") or section_ctx
    block = get("block") or block_ctx

    return SRDField(
        name=name,
        label=get("label") or name,
        field_type=_infer_type(get("type")),
        required=required_val,
        hide_expression=hide_expr,
        validation_rules=validation_rules,
        options=options,
        notes=get("notes") or None,
        section=section or None,
        block=block or None,
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
    fields = []
    section_ctx = block_ctx = ""
    for row in data:
        f = _row_to_field(row, col_map, section_ctx, block_ctx)
        if f:
            if f.section:
                section_ctx = f.section
            if f.block:
                block_ctx = f.block
            fields.append(f)
    return fields


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
            for row_line in block[2:]:  # skip separator row (index 1)
                row = [c.strip() for c in row_line.split("|")[1:-1]]
                if any(row):
                    data_rows.append(row)
            tables.append((headers, data_rows))
        else:
            i += 1
    return tables


def extract_metadata(content: str) -> Dict[str, Any]:
    """Extract pricing, workflow, SLA, and other metadata from markdown sections."""
    metadata: Dict[str, Any] = {}

    # Service name
    m = re.search(r'##\s*Service Name\s*\n+\*\*Eng\*\*:\s*(.+)', content, re.IGNORECASE)
    if m:
        metadata["service_name"] = m.group(1).strip()

    # SLA
    m = re.search(r'SLA\s*[-–]\s*(\d+\s*\w+)', content, re.IGNORECASE)
    if m:
        metadata["sla"] = m.group(1).strip()

    # Workflow
    m = re.search(r'Specify the workflow[^:]*:\s*\*\*?([^\n*]+)\*\*?', content, re.IGNORECASE)
    if not m:
        m = re.search(r'Specify new workflow here\s+([^\n]+)', content, re.IGNORECASE)
    if m:
        metadata["workflow"] = m.group(1).strip()

    # Pricing — is it free?
    pricing_section = re.search(
        r'#\s*Pricing(.+?)(?=\n#\s|\Z)', content, re.IGNORECASE | re.DOTALL
    )
    if pricing_section:
        blob = pricing_section.group(1)
        if re.search(r'not applicable because service is free', blob, re.IGNORECASE):
            metadata["pricing"] = "free"
        else:
            # Try to extract fixed amounts
            amounts = re.findall(r'(\d[\d,]*\s*RWF(?:\s*per\s*[^\n,]+)?)', blob, re.IGNORECASE)
            metadata["pricing"] = amounts if amounts else "see document"

    return metadata


async def parse_markdown(content: str) -> List[SRDField]:
    fields: List[SRDField] = []
    for headers, rows in _parse_markdown_tables(content):
        col_map = _build_col_map(headers)
        # Only process tables that look like form-field tables
        # (must have a "name" or "field name" column)
        if "name" not in col_map:
            continue
        section_ctx = block_ctx = ""
        for row in rows:
            f = _row_to_field(row, col_map, section_ctx, block_ctx)
            if f:
                if f.section:
                    section_ctx = f.section
                if f.block:
                    block_ctx = f.block
                fields.append(f)
    return fields


async def parse_srd_document(content: str) -> dict:
    """Parse a full SRD markdown document and return fields + metadata."""
    fields = await parse_markdown(content)
    metadata = extract_metadata(content)
    return {
        "fields": [f.model_dump() for f in fields],
        "metadata": metadata,
        "field_count": len(fields),
    }


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def parse_srd_url(url: str) -> List[SRDField]:
    if "notion.so" in url or "notion.com" in url:
        page_id = _extract_notion_page_id(url)
        return await _parse_notion_page(page_id)

    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return await parse_markdown(resp.text)
