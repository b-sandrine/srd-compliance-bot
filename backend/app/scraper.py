from __future__ import annotations
import asyncio
import os
import re
import sys
import time
from typing import List

from playwright.sync_api import sync_playwright, Page

from .models import FormField, FieldType


_TYPE_MAP = {
    "dropdown": FieldType.DROPDOWN,
    "select":   FieldType.DROPDOWN,
    "date":     FieldType.DATE,
    "datetime-local": FieldType.DATE,
    "file":     FieldType.FILE,
    "checkbox": FieldType.CHECKBOX,
    "radio":    FieldType.RADIO,
    "textarea": FieldType.TEXTAREA,
    "email":    FieldType.EMAIL,
    "tel":      FieldType.PHONE,
    "number":   FieldType.NUMBER,
    "text":     FieldType.TEXT,
}


def _infer_type(raw: str) -> FieldType:
    low = raw.lower().strip()
    for key, val in _TYPE_MAP.items():
        if key in low:
            return val
    return FieldType.UNKNOWN


# ---------------------------------------------------------------------------
# JavaScript injected into the page — targets NZ-ZORRO (Ant Design for Angular)
# which is what IremboGov uses, with a standard-HTML fallback.
# ---------------------------------------------------------------------------

_EXTRACT_JS = """
() => {
    const fields = [];
    const seen  = new Set();

    // ---- helpers -----------------------------------------------------------

    function labelText(el) {
        if (!el) return null;
        // Strip trailing asterisk (required marker) and whitespace
        return el.innerText.trim().replace(/\\s*[*✱]\\s*$/, '').trim() || null;
    }

    function getLabel(container) {
        const selectors = [
            '.ant-form-item-label > label',
            'nz-form-label label',
            '.ant-form-item-label label',
            'label',
        ];
        for (const sel of selectors) {
            const el = container.querySelector(sel);
            const t  = labelText(el);
            if (t) return t;
        }
        return null;
    }

    function getFieldName(container) {
        const attrs = ['formcontrolname', 'ng-reflect-name', 'data-field-name', 'name'];
        // Check the container itself then every descendant
        const candidates = [container, ...container.querySelectorAll('*')];
        for (const el of candidates) {
            for (const attr of attrs) {
                const v = el.getAttribute(attr);
                if (v && v.trim() && !v.startsWith('_ng') && v !== 'undefined') {
                    return v.trim();
                }
            }
        }
        // Fallback: id of the first real input inside
        const inp = container.querySelector('input[id], select[id], textarea[id]');
        if (inp) return inp.id || null;
        return null;
    }

    function getType(container) {
        if (container.querySelector('nz-select, .ant-select:not(.ant-picker)'))   return 'dropdown';
        if (container.querySelector('nz-date-picker, nz-time-picker, .ant-picker')) return 'date';
        if (container.querySelector('nz-upload, .ant-upload'))                     return 'file';
        if (container.querySelector('nz-radio-group, .ant-radio-wrapper'))         return 'radio';
        if (container.querySelector('nz-checkbox, .ant-checkbox-wrapper'))         return 'checkbox';
        if (container.querySelector('nz-input-number, .ant-input-number'))         return 'number';
        const inp = container.querySelector('input');
        if (inp) {
            const t = (inp.type || 'text').toLowerCase();
            if (t === 'hidden' || t === 'submit' || t === 'button') return 'unknown';
            return t;
        }
        if (container.querySelector('textarea')) return 'textarea';
        return 'unknown';
    }

    function isRequired(container) {
        if (container.querySelector(
            '.ant-form-item-required, [ng-reflect-nz-required="true"], [nzrequired]'
        )) return true;
        const lbl = container.querySelector('label');
        if (lbl && lbl.classList.contains('ant-form-item-required')) return true;
        const inp = container.querySelector('input, select, textarea');
        return !!(inp && (inp.required || inp.getAttribute('aria-required') === 'true'));
    }

    function isVisible(el) {
        const s = window.getComputedStyle(el);
        return s.display !== 'none' && s.visibility !== 'hidden' &&
               parseFloat(s.opacity) > 0 && el.offsetParent !== null;
    }

    function getHide(container) {
        const attrs = ['ng-if', 'data-ng-if', 'ng-show', 'data-ng-show', '*ngif'];
        let node = container;
        for (let d = 0; d < 6; d++) {
            if (!node) break;
            for (const a of attrs) {
                const v = node.getAttribute(a);
                if (v && v !== 'false' && v !== '') return a + ': ' + v;
            }
            node = node.parentElement;
        }
        return null;
    }

    function getOptions(container) {
        const opts = [];
        // NZ-ZORRO select options visible in the DOM
        container.querySelectorAll('.ant-select-item-option-content').forEach(o => {
            const t = o.innerText.trim();
            if (t) opts.push(t);
        });
        // Standard <select> options
        container.querySelectorAll('option').forEach(o => {
            if (o.value) opts.push(o.innerText.trim());
        });
        return opts;
    }

    function push(name, label, type, required, visible, hide, options, attrs) {
        if (!name && !label) return;
        const key = (name || '') + '||' + (label || '');
        if (seen.has(key)) return;
        seen.add(key);
        fields.push({ name, label, type, required, visible,
                      hide_expression: hide, options, attributes: attrs });
    }

    // ---- Strategy 1: NZ-ZORRO .ant-form-item / nz-form-item ---------------
    document.querySelectorAll('.ant-form-item, nz-form-item').forEach(item => {
        const hasControl = item.querySelector(
            'input, select, textarea, nz-select, nz-date-picker, nz-upload,' +
            ' nz-radio-group, nz-checkbox, nz-input-number, nz-time-picker'
        );
        if (!hasControl) return;

        push(
            getFieldName(item),
            getLabel(item),
            getType(item),
            isRequired(item),
            isVisible(item),
            getHide(item),
            getOptions(item),
            { class: item.className || null }
        );
    });

    // ---- Strategy 2: Angular Formly fields (if NZ-ZORRO didn't fire) -------
    if (fields.length === 0) {
        document.querySelectorAll('formly-field, [formlyfield]').forEach(item => {
            const hasControl = item.querySelector('input, select, textarea');
            if (!hasControl) return;
            push(
                getFieldName(item) || item.getAttribute('ng-reflect-key'),
                getLabel(item),
                getType(item),
                isRequired(item),
                isVisible(item),
                getHide(item),
                getOptions(item),
                {}
            );
        });
    }

    // ---- Strategy 3: plain HTML inputs (ultimate fallback) -----------------
    if (fields.length === 0) {
        document.querySelectorAll('input, select, textarea').forEach(el => {
            const t = (el.type || '').toLowerCase();
            if (['hidden','submit','button','reset','image'].includes(t)) return;

            let lbl = null;
            if (el.id) {
                const l = document.querySelector('label[for="' + el.id + '"]');
                if (l) lbl = labelText(l);
            }
            if (!lbl) {
                const parent = el.closest('.form-group, .form-field, [class*="field"]');
                if (parent) { const l = parent.querySelector('label'); if (l) lbl = labelText(l); }
            }
            if (!lbl) lbl = el.getAttribute('aria-label') || el.placeholder || null;

            const name = el.name || el.id || null;
            push(
                name, lbl,
                el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea' : t,
                el.required || el.getAttribute('aria-required') === 'true',
                isVisible(el),
                null,
                el.tagName === 'SELECT'
                    ? Array.from(el.options).filter(o => o.value).map(o => o.text.trim())
                    : [],
                { placeholder: el.placeholder || null }
            );
        });
    }

    return fields;
}
"""


# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

def _with_lang_en(url: str) -> str:
    if "lang=en" in url:
        return url
    if re.search(r'[?&]lang=', url):
        return re.sub(r'(lang=)[^&]+', r'\1en', url)
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}lang=en"


def _ensure_english(page: Page) -> None:
    try:
        if "lang=en" not in page.url:
            page.goto(_with_lang_en(page.url), wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Login step
# ---------------------------------------------------------------------------

def _try_login(page: Page) -> None:
    username = os.getenv("SERVICE_USERNAME", "") or "0789709595"
    password = os.getenv("SERVICE_PASSWORD", "") or "Test@123"
    if not username or not password:
        return
    try:
        # IremboGov uses phone number input; also accept email/username fields
        user_sel = (
            'input[type="tel"], input[name="phone"], input[id*="phone"], '
            'input[type="email"], input[name="email"], input[name="username"]'
        )
        if page.locator(user_sel).count():
            page.fill(user_sel, username)
            page.fill('input[type="password"]', password)
            page.click(
                'button[type="submit"], input[type="submit"], '
                '.login-btn, .btn-login, button:has-text("Login"), button:has-text("Sign in")'
            )
            page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sync scraper — called inside asyncio.to_thread()
# ---------------------------------------------------------------------------

def _scrape_sync(service_url: str) -> List[FormField]:
    # On Windows, sync_playwright's internal greenlet needs ProactorEventLoop
    # to be able to spawn Chromium subprocesses.
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])

        # Inject lang cookie before any navigation so the server sends English HTML
        parsed = re.search(r'https?://([^/]+)', service_url)
        domain = parsed.group(1) if parsed else ""

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        if domain:
            context.add_cookies([
                {"name": "lang",     "value": "en", "domain": domain, "path": "/"},
                {"name": "language", "value": "en", "domain": domain, "path": "/"},
            ])

        page = context.new_page()
        try:
            # Navigate with lang=en baked into the URL
            page.goto(_with_lang_en(service_url), wait_until="domcontentloaded", timeout=30000)
            _try_login(page)
            _ensure_english(page)  # re-apply if login redirect dropped lang param

            # Wait for NZ-ZORRO or standard form elements to appear
            try:
                page.wait_for_selector(
                    ".ant-form-item, nz-form-item, "
                    "form, [role='form'], [formlyfield], mat-form-field",
                    timeout=15000,
                )
            except Exception:
                pass

            # Extra settle time for Angular change detection to finish rendering
            time.sleep(3)

            raw_fields: list = page.evaluate(_EXTRACT_JS) or []
        finally:
            browser.close()

    form_fields: List[FormField] = []
    for fd in raw_fields:
        name  = fd.get("name")  or ""
        label = fd.get("label") or ""
        if not name and not label:
            continue

        form_fields.append(FormField(
            name=name   or None,
            label=label or None,
            field_type=_infer_type(fd.get("type", "")),
            required=bool(fd.get("required", False)),
            visible=bool(fd.get("visible", True)),
            hide_expression=fd.get("hide_expression"),
            options=fd.get("options", []),
            attributes=fd.get("attributes", {}),
        ))

    return form_fields


# ---------------------------------------------------------------------------
# Public async entry point
# ---------------------------------------------------------------------------

async def scrape_service(service_url: str) -> List[FormField]:
    """Run the sync Playwright scraper in a thread pool to keep the async loop unblocked."""
    return await asyncio.to_thread(_scrape_sync, service_url)
