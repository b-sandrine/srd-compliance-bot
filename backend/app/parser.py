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
    "dropdown selector": FieldType.DROPDOWN,
    "information list": FieldType.TEXT,   
    "nid widget": FieldType.TEXT,
    "tin widget": FieldType.TEXT,
    "id widget": FieldType.TEXT,
    "tin fetch": FieldType.TEXT,
    "tin": FieldType.TEXT,
    "id fetch": FieldType.TEXT,
    "nid fetch": FieldType.TEXT,
}


def _infer_type(raw: str) -> FieldType:
    low = raw.lower().strip()
    for key in sorted(_TYPE_MAP.keys(), key=len, reverse=True):
        if key in low:
            return _TYPE_MAP[key]
    return FieldType.UNKNOWN


def _infer_required(raw: str) -> Optional[bool]:
    low = raw.lower().strip()
    if not low:
        return None  
    if low in ("yes", "true", "required", "mandatory", "y", "1", "✓", "✔"):
        return True
    if low in ("no", "false", "optional", "n", "0", "–", "-"):
        return False
    return None


def _required_from_validation(validation_raw: str) -> Optional[bool]:
    low = validation_raw.lower()
    if re.search(r"\brequired\b", low) and not re.search(r"\boptional\b", low):
        return True
    if re.search(r"\boptional\b", low):
        return False
    return None


def _extract_options(raw: str) -> List[str]:
    if not raw:
        return []

    options: List[str] = []
    # Strip common structural header noise inside the cells
    clean_raw = re.sub(r'(placeholder|list of values|dropdown values|values?):', '', raw, flags=re.IGNORECASE).strip()
    
    for line in clean_raw.splitlines():
        stripped = line.strip()
        # Clean off numbered lists (1. Text) or bullet arrays (- Text / * Text)
        m = re.match(r'^(?:\d+[\.\)]|[-•*])\s*(.*)', stripped)
        if m:
            item = m.group(1).strip()
        else:
            item = stripped
            
        item = re.sub(r'\*\*([^*]+)\*\*', r'\1', item).strip()
        if item and item.lower() not in ("n/a", "na", ""):
            options.append(item)

    return [o for o in options if o]


def _clean_display_rule(raw: str) -> Optional[str]:
    if not raw:
        return None
    low = raw.lower().strip()
    if low in ("", "always on display", "always displayed", "always visible", "n/a", "na", "-"):
        return None
    return raw.strip()


# ---------------------------------------------------------------------------
# Column-header mapping
# ---------------------------------------------------------------------------

_COL_KEYWORDS: Dict[str, List[str]] = {
    "section":         ["section"],
    "block":           ["block"],
    "name":            ["field name", "component name", "name", "key"],
    "label":           ["label", "display name", "title"],
    "type":            ["field type", "data type", "input type", "type"],
    "required":        ["required", "mandatory", "obligatory"],
    "options":         ["list of values", "placeholder", "option", "choice", "enum", "value"],
    "notes":           ["tooltip", "hint", "note", "remark", "comment", "description"],
    "widget_req":      ["widget requirement", "widget"],
    "validation":      ["validation rule", "validation", "constraint"],
    "error":           ["error message", "error"],
    "hide_expression": ["display rule", "display condition", "hide expression",
                        "show when", "visible when", "hide", "condition", "visibility"],
}


def _build_col_map(headers: List[str]) -> dict:
    col_map: dict = {}
    for idx, col in enumerate(headers):
        low = col.lower().strip()
        for key, keywords in _COL_KEYWORDS.items():
            if key not in col_map and any(kw in low for kw in keywords):
                col_map[key] = idx
    return col_map

# ---------------------------------------------------------------------------
# Core Stateful Transformer Engine
# ---------------------------------------------------------------------------

def _process_compiled_rows(headers: List[str], raw_rows: List[List[str]]) -> List[SRDField]:
    col_map = _build_col_map(headers)
    fields: List[SRDField] = []
    
    state_ctx = {"section": "", "block": ""}
    
    name_idx = col_map.get("name")
    type_idx = col_map.get("type")
    
    if name_idx is None:
        return []

    for cells in raw_rows:
        # Step A: Safe evaluation of structural headers
        sec_val = cells[col_map.get("section")].strip() if col_map.get("section") is not None else ""
        blk_val = cells[col_map.get("block")].strip() if col_map.get("block") is not None else ""
        
        if sec_val: state_ctx["section"] = sec_val
        if blk_val: state_ctx["block"] = blk_val

        raw_name = cells[name_idx].strip()
        raw_type = cells[type_idx].strip() if type_idx is not None else ""

        # Step B: Guard against accidental list items matching names (e.g. "- Company")
        is_new_field = bool(raw_name and not re.match(r'^[-•*\d]', raw_name))

        if is_new_field:
            def get_cell(key: str) -> str:
                idx = col_map.get(key)
                return cells[idx].strip() if (idx is not None and idx < len(cells)) else ""

            validation_raw = get_cell("validation")
            validation_rules = [v.strip() for v in re.split(r"[;\n]", validation_raw) if v.strip()] if validation_raw else []

            required_val = _infer_required(get_cell("required"))
            if required_val is None and validation_raw:
                required_val = _required_from_validation(validation_raw)

            widget_req_raw = get_cell("widget_req")
            widget_req = None if (not widget_req_raw or widget_req_raw.lower() in ("n/a", "na", "-", "–")) else widget_req_raw

            field_obj = SRDField(
                name=raw_name,
                label=get_cell("label") or raw_name,
                field_type=_infer_type(raw_type),
                required=required_val,
                hide_expression=_clean_display_rule(get_cell("hide_expression")),
                validation_rules=validation_rules,
                options=_extract_options(get_cell("options")),
                notes=get_cell("notes") or None,
                widget_requirements=widget_req,
                section=state_ctx.get("section") or None,
                block=state_ctx.get("block") or None,
            )
            fields.append(field_obj)
            
        elif fields:
            # Step C: Append multi-line cell text blocks straight down to active object
            target_field = fields[-1]
            
            for key, idx in col_map.items():
                if idx >= len(cells): continue
                append_val = cells[idx].strip()
                if not append_val or append_val.lower() in ("n/a", "na"): continue
                
                if key == "options":
                    target_field.options.extend(_extract_options(append_val))
                    target_field.options = list(dict.fromkeys(target_field.options))
                elif key == "validation":
                    new_rules = [v.strip() for v in re.split(r"[;\n]", append_val) if v.strip()]
                    target_field.validation_rules.extend(new_rules)
                elif key == "hide_expression":
                    cleaned_expr = _clean_display_rule(append_val)
                    if cleaned_expr:
                        target_field.hide_expression = (target_field.hide_expression or "") + "\n" + cleaned_expr

    return fields


# ---------------------------------------------------------------------------
# Reconstructed Markdown Table Engine (Corrects Column Alignment Shifts)
# ---------------------------------------------------------------------------

def _parse_markdown_tables(content: str) -> List[Tuple[List[str], List[List[str]]]]:
    """
    Parses raw markdown text tables cleanly by gathering true structural block 
    rows using cell indices first, avoiding data corruption caused by raw string splits.
    """
    tables = []
    lines = content.splitlines()
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("|"):
            i += 1
            continue

        # Isolate the structured block boundary
        raw_table_lines = []
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith("|"):
                raw_table_lines.append(stripped)
                i += 1
            else:
                break

        if len(raw_table_lines) < 3:
            continue

        # Extract clean headers
        headers = [c.strip() for c in raw_table_lines[0].split("|")[1:-1]]
        data_rows: List[List[str]] = []

        # Iterate past structural header boundaries
        for row_line in raw_table_lines[2:]:
            # Standard cell splitter
            cells = [c.strip() for c in row_line.split("|")[1:-1]]
            
            if re.match(r'^[-:| ]+$', "".join(cells)):
                continue
                
            # Keep array sizing synchronized across wide columns
            while len(cells) < len(headers):
                cells.append("")
            cells = cells[:len(headers)]

            # Check if this row is a clean continuation row
            non_empty_indices = [idx for idx, cell in enumerate(cells) if cell]
            
            # If the row only contains bullet markers or hanging indentation text,
            # we flag it as an operational block modification row
            is_bullet_continuation = False
            if len(non_empty_indices) == 1:
                target_idx = non_empty_indices[0]
                if cells[target_idx].startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5.")):
                    is_bullet_continuation = True

            if data_rows and is_bullet_continuation:
                # Merge elements into preceding object cells
                data_rows[-1][target_idx] += "\n" + cells[target_idx]
            else:
                if any(cells):
                    data_rows.append(cells)

        tables.append((headers, data_rows))
    return tables


async def parse_markdown(content: str) -> List[SRDField]:
    fields: List[SRDField] = []
    for headers, rows in _parse_markdown_tables(content):
        col_map = _build_col_map(headers)
        if "name" not in col_map:
            continue
        compiled_fields = _process_compiled_rows(headers, rows)
        fields.extend(compiled_fields)
    return fields


# ---------------------------------------------------------------------------
# Notion entries / Metadata API connectors
# ---------------------------------------------------------------------------

async def _parse_notion_table(notion: NotionClient, table_block: dict) -> List[SRDField]:
    has_header = table_block["table"].get("has_column_header", True)
    rows_resp = await notion.blocks.children.list(block_id=table_block["id"])
    rows = rows_resp["results"]
    if not rows: return []

    parsed_rows = [[_rich_text(cell) for cell in row["table_row"]["cells"]] for row in rows]
    if has_header and len(parsed_rows) > 1:
        headers = parsed_rows[0]
        data = parsed_rows[1:]
    else:
        headers, data = [], parsed_rows

    return _process_compiled_rows(headers, data)


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


def extract_metadata(content: str) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    m = re.search(r'##\s*Service Name\s*\n+\*\*Eng\*\*:\s*(.+)', content, re.IGNORECASE)
    if m: metadata["service_name"] = m.group(1).strip()
    m = re.search(r'SLA\s*[-–]\s*(\d+\s*\w+)', content, re.IGNORECASE)
    if m: metadata["sla"] = m.group(1).strip()
    return metadata


async def parse_srd_document(content: str) -> dict:
    fields = await parse_markdown(content)
    metadata = extract_metadata(content)
    return {
        "fields": [f.model_dump() for f in fields],
        "metadata": metadata,
        "field_count": len(fields)
    }


async def parse_srd_url(url: str) -> List[SRDField]:
    if "notion.so" in url or "notion.com" in url:
        return await _parse_notion_page(_extract_notion_page_id(url))
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return await parse_markdown(resp.text)