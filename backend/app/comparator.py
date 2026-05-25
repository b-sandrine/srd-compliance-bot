from __future__ import annotations
import re
from typing import List, Optional

from .models import SRDField, FormField, FieldMismatch, ComparisonReport


def _normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _find_form_match(srd: SRDField, form_fields: List[FormField]) -> Optional[int]:
    """Return index of the best-matching FormField, or None."""
    srd_name = _normalize(srd.name)
    srd_label = _normalize(srd.label)

    exact_idx: Optional[int] = None
    partial_idx: Optional[int] = None

    for i, ff in enumerate(form_fields):
        ff_name = _normalize(ff.name)
        ff_label = _normalize(ff.label)

        # Exact name match — highest priority
        if srd_name and ff_name and srd_name == ff_name:
            return i

        # Exact label match
        if srd_label and ff_label and srd_label == ff_label:
            if exact_idx is None:
                exact_idx = i

        # Substring match (one contains the other)
        if srd_name and ff_name and (srd_name in ff_name or ff_name in srd_name):
            if partial_idx is None:
                partial_idx = i
        if srd_label and ff_label and (srd_label in ff_label or ff_label in srd_label):
            if partial_idx is None:
                partial_idx = i

    return exact_idx if exact_idx is not None else partial_idx


def _check_mismatch(
    field_name: str,
    prop: str,
    srd_val,
    form_val,
    severity: str = "warning",
) -> Optional[FieldMismatch]:
    if srd_val == form_val:
        return None
    return FieldMismatch(
        field_name=field_name,
        property=prop,
        srd_value=srd_val,
        form_value=form_val,
        severity=severity,
    )


def compare_srd_with_form(
    job_id: str,
    service_url: str,
    srd_source: str,
    srd_fields: List[SRDField],
    form_fields: List[FormField],
) -> ComparisonReport:
    matched_srd: set = set()
    matched_form: set = set()
    matching_names: List[str] = []
    mismatches: List[FieldMismatch] = []

    for i, srd in enumerate(srd_fields):
        j = _find_form_match(srd, form_fields)
        if j is None:
            continue

        matched_srd.add(i)
        matched_form.add(j)
        matching_names.append(srd.name)
        ff = form_fields[j]

        # --- type ---
        if srd.field_type != "unknown" and ff.field_type != "unknown":
            m = _check_mismatch(srd.name, "field_type", srd.field_type, ff.field_type, "error")
            if m:
                mismatches.append(m)

        # --- required ---
        if srd.required is not None and ff.required is not None:
            m = _check_mismatch(srd.name, "required", srd.required, ff.required, "error")
            if m:
                mismatches.append(m)

        # --- hide expression presence ---
        has_srd_hide = bool(srd.hide_expression)
        has_form_hide = bool(ff.hide_expression)
        if has_srd_hide != has_form_hide:
            mismatches.append(FieldMismatch(
                field_name=srd.name,
                property="hide_expression",
                srd_value=srd.hide_expression,
                form_value=ff.hide_expression,
                severity="warning",
            ))

        # --- visibility (field should be visible if no hide expression) ---
        if not has_srd_hide and not ff.visible:
            mismatches.append(FieldMismatch(
                field_name=srd.name,
                property="visible",
                srd_value=True,
                form_value=False,
                severity="warning",
            ))

    missing_from_form = [srd_fields[i] for i in range(len(srd_fields)) if i not in matched_srd]
    extra_in_form = [form_fields[j] for j in range(len(form_fields)) if j not in matched_form]

    total_srd = len(srd_fields)
    compliance_score = round(len(matching_names) / total_srd * 100, 1) if total_srd else 0.0

    summary = {
        "total_srd_fields": total_srd,
        "total_form_fields": len(form_fields),
        "matched_fields": len(matching_names),
        "missing_from_form": len(missing_from_form),
        "extra_in_form": len(extra_in_form),
        "property_mismatches": len(mismatches),
        "compliance_score": compliance_score,
    }

    return ComparisonReport(
        job_id=job_id,
        service_url=service_url,
        srd_source=srd_source,
        matching_fields=matching_names,
        missing_from_form=missing_from_form,
        extra_in_form=extra_in_form,
        mismatches=mismatches,
        summary=summary,
        raw_srd_fields=srd_fields,
        raw_form_fields=form_fields,
    )
