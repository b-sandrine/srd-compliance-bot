import React, { useState } from 'react';

function JsonPanel({ title, data }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-slate-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left p-3 bg-slate-900 text-slate-300 text-sm font-semibold flex justify-between items-center hover:bg-slate-800 transition-colors"
      >
        {title}
        <span className="text-slate-500 text-xs">{open ? '▲ collapse' : '▼ expand'}</span>
      </button>
      {open && (
        <pre className="bg-slate-950 p-4 text-xs text-emerald-300 overflow-x-auto max-h-96 overflow-y-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function SeverityBadge({ severity }) {
  const cls =
    severity === 'error'
      ? 'bg-rose-500/20 text-rose-400 border border-rose-700'
      : severity === 'warning'
      ? 'bg-amber-500/20 text-amber-400 border border-amber-700'
      : 'bg-slate-700 text-slate-400 border border-slate-600';
  return <span className={`px-2 py-0.5 rounded text-xs font-bold ${cls}`}>{severity}</span>;
}

export default function ReportView({ report }) {
  const {
    compliant,
    summary,
    matching_fields,
    missing_from_form,
    extra_in_form,
    mismatches,
    raw_srd_fields,
    raw_form_fields,
    service_url,
    srd_source,
  } = report;

  const score = summary?.compliance_score ?? 0;

  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold">Audit Results</h2>
        <span
          className={`px-4 py-1.5 rounded-full text-sm font-bold ${
            compliant
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500'
              : 'bg-rose-500/20 text-rose-400 border border-rose-500'
          }`}
        >
          {compliant ? '✓ Compliant with SRD' : '✗ Drift Detected'}
        </span>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center">
        {[
          { label: 'SRD Fields', value: summary?.total_srd_fields ?? 0, color: 'text-slate-300' },
          { label: 'Form Fields', value: summary?.total_form_fields ?? 0, color: 'text-slate-300' },
          { label: 'Matched', value: summary?.matched_fields ?? 0, color: 'text-emerald-400' },
          { label: 'Missing', value: summary?.missing_from_form ?? 0, color: 'text-rose-400' },
          { label: 'Extra', value: summary?.extra_in_form ?? 0, color: 'text-cyan-400' },
          {
            label: 'Score',
            value: `${score}%`,
            color: score >= 80 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-rose-400',
          },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-900 rounded-lg p-3 border border-slate-700">
            <div className={`text-xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Property mismatches */}
      {mismatches.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-amber-400 font-semibold text-lg">⚠ Property Mismatches</h3>
          <div className="overflow-x-auto rounded-lg border border-slate-700">
            <table className="w-full text-left border-collapse bg-slate-950 text-sm">
              <thead>
                <tr className="bg-slate-900 border-b border-slate-700 text-slate-400">
                  <th className="p-3">Severity</th>
                  <th className="p-3">Field</th>
                  <th className="p-3">Property</th>
                  <th className="p-3">Expected (SRD)</th>
                  <th className="p-3">Actual (Form)</th>
                </tr>
              </thead>
              <tbody>
                {mismatches.map((m, i) => (
                  <tr key={i} className="border-b border-slate-800">
                    <td className="p-3"><SeverityBadge severity={m.severity} /></td>
                    <td className="p-3 font-mono text-indigo-300">{m.field_name}</td>
                    <td className="p-3 text-slate-400">{m.property}</td>
                    <td className="p-3 text-emerald-400 font-mono">{String(m.srd_value)}</td>
                    <td className="p-3 text-rose-400 font-mono">{String(m.form_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Missing from form */}
      {missing_from_form.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-rose-400 font-semibold text-lg">❌ Missing in Production (defined in SRD)</h3>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {missing_from_form.map((f, i) => (
              <li key={i} className="bg-slate-900 p-3 rounded-lg border border-rose-900/30 text-sm font-mono flex justify-between">
                <span className="text-slate-300">{f.name}</span>
                <span className="text-slate-500">{f.field_type}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Extra in form */}
      {extra_in_form.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-cyan-400 font-semibold text-lg">➕ Undocumented Production Fields</h3>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {extra_in_form.map((f, i) => (
              <li key={i} className="bg-slate-900 p-3 rounded-lg border border-cyan-900/30 text-sm font-mono flex justify-between">
                <span className="text-slate-300">{f.label || f.name || '(unnamed)'}</span>
                <span className="text-slate-500">{f.field_type}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {compliant && (
        <div className="bg-emerald-950/30 border border-emerald-800 p-4 rounded-lg text-emerald-400 text-center font-medium">
          The production form matches the SRD specification.
        </div>
      )}

      {/* Raw JSON panels for comparison */}
      <div className="space-y-3 pt-2">
        <h3 className="text-slate-400 font-semibold text-base">Raw JSON (for manual review)</h3>
        <JsonPanel
          title={`📄 SRD Fields (${raw_srd_fields.length}) — parsed from ${srd_source}`}
          data={raw_srd_fields}
        />
        <JsonPanel
          title={`🌐 Live Form Fields (${raw_form_fields.length}) — scraped from ${service_url}`}
          data={raw_form_fields}
        />
        <JsonPanel title="📊 Full Comparison Report" data={report} />
      </div>
    </div>
  );
}
