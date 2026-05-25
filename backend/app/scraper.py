from __future__ import annotations
import asyncio
import os
import time
from typing import List

# Use the SYNC Playwright API and run it inside asyncio.to_thread().
# The async Playwright API calls asyncio.create_subprocess_exec, which requires
# ProactorEventLoop — but uvicorn on Windows uses SelectorEventLoop, causing
# NotImplementedError. The sync API manages its own subprocess transport and
# works correctly when dispatched to a thread pool.
from playwright.sync_api import sync_playwright, Page

from .models import FormField, FieldType


_TYPE_MAP = {
    "text": FieldType.TEXT,
    "number": FieldType.NUMBER,
    "date": FieldType.DATE,
    "datetime-local": FieldType.DATE,
    "select": FieldType.DROPDOWN,
    "file": FieldType.FILE,
    "checkbox": FieldType.CHECKBOX,
    "radio": FieldType.RADIO,
    "textarea": FieldType.TEXTAREA,
    "email": FieldType.EMAIL,
    "tel": FieldType.PHONE,
}


def _infer_type(raw: str) -> FieldType:
    low = raw.lower().strip()
    for key, val in _TYPE_MAP.items():
        if key in low:
            return val
    return FieldType.UNKNOWN


# ---------------------------------------------------------------------------
# JavaScript injected into the page to extract form field metadata
# ---------------------------------------------------------------------------

_EXTRACT_JS = """
() => {
    const fields = [];

    function getLabel(el) {
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) return lbl.innerText.trim();
        }
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) return ariaLabel.trim();

        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const lblEl = document.getElementById(labelledBy);
            if (lblEl) return lblEl.innerText.trim();
        }

        const parent = el.closest(
            '.form-group, .form-field, [class*="field"], [class*="input-group"],' +
            ' .ant-form-item, .mat-form-field, .MuiFormControl-root,' +
            ' nz-form-item, .el-form-item, [formlyfield], [formly-field]'
        );
        if (parent) {
            const lblEl = parent.querySelector('label, .label, [class*="label"], .field-label');
            if (lblEl && lblEl !== el) return lblEl.innerText.trim();
        }

        return el.placeholder || el.getAttribute('data-label') || el.name || null;
    }

    function getHideExpression(el) {
        const attrs = [
            'ng-if', 'ng-show', 'ng-hide',
            'data-ng-if', 'data-ng-show', 'data-ng-hide',
            'v-if', 'v-show',
            'data-hide', 'data-show', 'data-condition',
            'data-hide-expression', 'data-visible-when',
            'formly-hide-expression', 'data-formly-hide-expression',
            '[hidden]', 'hidden'
        ];
        let node = el;
        for (let depth = 0; depth < 6; depth++) {
            if (!node) break;
            for (const attr of attrs) {
                const val = node.getAttribute(attr);
                if (val && val !== 'false' && val !== '') {
                    return attr + ': ' + val;
                }
            }
            node = node.parentElement;
        }
        return null;
    }

    function isVisible(el) {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' &&
               style.visibility !== 'hidden' &&
               parseFloat(style.opacity) > 0 &&
               el.offsetParent !== null;
    }

    function getOptions(el) {
        if (el.tagName === 'SELECT') {
            return Array.from(el.options)
                .filter(o => o.value !== '')
                .map(o => o.text.trim());
        }
        return [];
    }

    // Standard HTML inputs
    document.querySelectorAll('input, select, textarea').forEach(el => {
        const t = (el.type || '').toLowerCase();
        if (['hidden', 'submit', 'button', 'reset', 'image'].includes(t)) return;

        fields.push({
            name: el.name || el.id || null,
            label: getLabel(el),
            type: el.tagName === 'SELECT' ? 'select' : (el.tagName === 'TEXTAREA' ? 'textarea' : t),
            required: el.required || el.getAttribute('aria-required') === 'true',
            visible: isVisible(el),
            hide_expression: getHideExpression(el),
            options: getOptions(el),
            attributes: {
                placeholder: el.placeholder || null,
                'data-field-name': el.getAttribute('data-field-name'),
                'data-name': el.getAttribute('data-name'),
                'data-field-type': el.getAttribute('data-field-type'),
                class: el.className || null,
            }
        });
    });

    // Custom / framework components that wrap inputs
    const customSelectors = [
        '[formlyfield]', '[formly-field]', '.formly-field',
        'mat-form-field', 'nz-form-item', 'el-form-item',
        '[data-field-type]', '[data-component-type="field"]',
    ].join(', ');

    document.querySelectorAll(customSelectors).forEach(el => {
        if (el.querySelector('input, select, textarea')) return;

        const lblEl = el.querySelector('label, .label, [class*="label"], .field-label');
        fields.push({
            name: el.getAttribute('data-field-name') || el.getAttribute('name') || el.id || null,
            label: lblEl ? lblEl.innerText.trim() : null,
            type: el.getAttribute('data-field-type') || el.getAttribute('data-component-type') || 'custom',
            required: el.getAttribute('data-required') === 'true' || el.hasAttribute('required'),
            visible: isVisible(el),
            hide_expression: getHideExpression(el),
            options: [],
            attributes: {
                class: el.className || null,
                'data-field-type': el.getAttribute('data-field-type'),
            }
        });
    });

    // Deduplicate by (name, label) in JS before returning
    const seen = new Set();
    return fields.filter(f => {
        const key = (f.name || '') + '||' + (f.label || '');
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}
"""


# ---------------------------------------------------------------------------
# Optional login step (sync version)
# ---------------------------------------------------------------------------

def _try_login(page: Page) -> None:
    username = os.getenv("SERVICE_USERNAME", "") or '0789709595'
    password = os.getenv("SERVICE_PASSWORD", "") or 'Test@123'
    if not username or not password:
        return
    try:
        if page.locator('input[type="email"], input[name="email"], input[name="username"]').count():
            page.fill('input[type="email"], input[name="email"], input[name="username"]', username)
            page.fill('input[type="password"]', password)
            page.click('button[type="submit"], input[type="submit"], .login-btn, .btn-login')
            page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sync scraper — called inside asyncio.to_thread() to avoid the
# ProactorEventLoop requirement of async Playwright on Windows
# ---------------------------------------------------------------------------

def _scrape_sync(service_url: str) -> List[FormField]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto(service_url, wait_until="domcontentloaded", timeout=30000)
            _try_login(page)

            try:
                page.wait_for_selector(
                    "form, [role='form'], .form-container, .application-form, "
                    "[formlyfield], mat-form-field, nz-form-item",
                    timeout=12000,
                )
            except Exception:
                pass

            time.sleep(2)  # allow dynamic frameworks to settle

            raw_fields: list = page.evaluate(_EXTRACT_JS)
        finally:
            browser.close()

    form_fields: List[FormField] = []
    for fd in raw_fields:
        name = fd.get("name") or ""
        label = fd.get("label") or ""
        if not name and not label:
            continue

        form_fields.append(FormField(
            name=name or None,
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
