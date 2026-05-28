import React, { useState, useMemo } from 'react';

const TYPE_COLORS = {
  dropdown:    'bg-purple-500/20 text-purple-300 border-purple-700',
  text:        'bg-blue-500/20 text-blue-300 border-blue-700',
  textarea:    'bg-blue-500/20 text-blue-300 border-blue-700',
  number:      'bg-orange-500/20 text-orange-300 border-orange-700',
  file:        'bg-yellow-500/20 text-yellow-300 border-yellow-700',
  email:       'bg-teal-500/20 text-teal-300 border-teal-700',
  phone:       'bg-teal-500/20 text-teal-300 border-teal-700',
  date:        'bg-indigo-500/20 text-indigo-300 border-indigo-700',
  checkbox:    'bg-emerald-500/20 text-emerald-300 border-emerald-700',
  radio:       'bg-emerald-500/20 text-emerald-300 border-emerald-700',
  multiselect: 'bg-purple-500/20 text-purple-300 border-purple-700',
  unknown:     'bg-slate-700 text-slate-400 border-slate-600',
};

function TypeBadge({ type }) {
  const cls = TYPE_COLORS[type] ?? TYPE_COLORS.unknown;
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-semibold ${cls}`}>
      {type}
    </span>
  );
}

function RequiredBadge({ required }) {
  if (required === true)
    return <span className="px-2 py-0.5 rounded border text-xs font-semibold bg-rose-500/20 text-rose-400 border-rose-700">required</span>;
  if (required === false)
    return <span className="px-2 py-0.5 rounded border text-xs font-semibold bg-slate-700 text-slate-400 border-slate-600">optional</span>;
  return <span className="text-slate-600 text-xs">—</span>;
}

function MetaCard({ label, value, color = 'text-slate-300' }) {
  if (!value) return null;
  return (
    <div className="bg-slate-900 rounded-lg p-3 border border-slate-700 space-y-0.5">
      <div className="text-xs text-slate-500 uppercase tracking-wide">{label}</div>
      <div className={`text-sm font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function TabButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-semibold rounded-t-lg border-b-2 transition-colors ${
        active
          ? 'border-indigo-500 text-indigo-300 bg-slate-800'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
      }`}
    >
      {label}
    </button>
  );
}

function FieldsTab({ fields, field_count }) {
  const [search, setSearch] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');

  const sections = useMemo(
    () => [...new Set(fields.map((f) => f.section).filter(Boolean))],
    [fields]
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return fields.filter((f) => {
      const matchSearch =
        !q ||
        (f.name || '').toLowerCase().includes(q) ||
        (f.section || '').toLowerCase().includes(q) ||
        (f.block || '').toLowerCase().includes(q) ||
        (f.field_type || '').toLowerCase().includes(q);
      const matchSection = !sectionFilter || f.section === sectionFilter;
      return matchSearch && matchSection;
    });
  }, [fields, search, sectionFilter]);

  return (
    <>
      <div className="flex flex-wrap gap-3 px-5 py-3 bg-slate-900/50 border-b border-slate-700">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search fields…"
          className="flex-1 min-w-48 p-2 rounded-lg bg-slate-950 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 placeholder-slate-600"
        />
        <select
          value={sectionFilter}
          onChange={(e) => setSectionFilter(e.target.value)}
          className="p-2 rounded-lg bg-slate-950 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
        >
          <option value="">All sections</option>
          {sections.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="self-center text-xs text-slate-500">
          {filtered.length} / {field_count} shown
        </span>
      </div>

      <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
        <table className="w-full text-left border-collapse text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="bg-slate-900 border-b border-slate-700 text-slate-400 text-xs uppercase tracking-wide">
              <th className="p-3 w-32">Section</th>
              <th className="p-3 w-32">Block</th>
              <th className="p-3">Field Name</th>
              <th className="p-3 w-28">Type</th>
              <th className="p-3 w-24">Required</th>
              <th className="p-3 w-40">Options</th>
              <th className="p-3 w-40">Widget Req.</th>
              <th className="p-3">Display Rule</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f, i) => (
              <tr
                key={i}
                className={`border-b border-slate-800 hover:bg-slate-700/30 transition-colors ${
                  i % 2 === 0 ? '' : 'bg-slate-900/20'
                }`}
              >
                <td className="p-3 text-slate-500 text-xs">{f.section || '—'}</td>
                <td className="p-3 text-slate-500 text-xs">{f.block || '—'}</td>
                <td className="p-3">
                  <span className="font-medium text-slate-200">{f.name}</span>
                  {f.label && f.label !== f.name && (
                    <span className="block text-xs text-slate-500">{f.label}</span>
                  )}
                </td>
                <td className="p-3"><TypeBadge type={f.field_type} /></td>
                <td className="p-3"><RequiredBadge required={f.required} /></td>
                <td className="p-3">
                  {f.options?.length > 0 ? (
                    <details className="cursor-pointer">
                      <summary className="text-xs text-indigo-400 hover:text-indigo-300">
                        {f.options.length} value{f.options.length !== 1 ? 's' : ''}
                      </summary>
                      <ul className="mt-1 space-y-0.5 max-h-28 overflow-y-auto">
                        {f.options.map((o, j) => (
                          <li key={j} className="text-xs text-slate-400 font-mono">• {o}</li>
                        ))}
                      </ul>
                    </details>
                  ) : (
                    <span className="text-slate-600 text-xs">—</span>
                  )}
                </td>
                <td className="p-3">
                  {f.widget_requirements ? (
                    <span className="text-xs text-cyan-400 font-mono">{f.widget_requirements}</span>
                  ) : (
                    <span className="text-slate-600 text-xs">—</span>
                  )}
                </td>
                <td className="p-3">
                  {f.hide_expression ? (
                    <span className="text-xs text-amber-400 italic">{f.hide_expression}</span>
                  ) : (
                    <span className="text-xs text-emerald-600">Always visible</span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="p-8 text-center text-slate-500">No fields match your filter.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function WorkflowTab({ metadata }) {
  const { workflow, sla, status_labels } = metadata;
  if (!workflow && !sla && !status_labels?.length) {
    return (
      <div className="p-8 text-center text-slate-500">No workflow information extracted.</div>
    );
  }
  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {workflow && (
          <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
            <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Workflow</div>
            <div className="text-sm font-semibold text-indigo-300">{workflow}</div>
          </div>
        )}
        {sla && (
          <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
            <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">SLA</div>
            <div className="text-sm font-semibold text-amber-300">{sla}</div>
          </div>
        )}
      </div>

      {status_labels?.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Status Labels</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-900 border-b border-slate-700 text-slate-400 text-xs uppercase tracking-wide">
                  <th className="p-3">Status</th>
                  <th className="p-3">Label</th>
                  <th className="p-3">Description</th>
                </tr>
              </thead>
              <tbody>
                {status_labels.map((row, i) => (
                  <tr key={i} className="border-b border-slate-800 hover:bg-slate-700/30">
                    <td className="p-3 text-slate-300 font-medium">{row.status || '—'}</td>
                    <td className="p-3 text-indigo-300">{row.label || '—'}</td>
                    <td className="p-3 text-slate-400 text-xs">{row.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function PricingTab({ metadata }) {
  const { pricing } = metadata;
  if (!pricing) {
    return (
      <div className="p-8 text-center text-slate-500">No pricing information extracted.</div>
    );
  }

  const isFree = pricing === 'free';
  const amounts = Array.isArray(pricing) ? pricing : null;

  return (
    <div className="p-6 space-y-4">
      <div className={`rounded-lg p-5 border ${isFree ? 'border-emerald-700 bg-emerald-900/20' : 'border-slate-700 bg-slate-900'}`}>
        <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Pricing Model</div>
        {isFree ? (
          <div className="text-lg font-bold text-emerald-400">Free Service</div>
        ) : amounts ? (
          <ul className="space-y-2 mt-2">
            {amounts.map((a, i) => (
              <li key={i} className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                {a}
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-sm text-slate-400">{pricing}</div>
        )}
      </div>
    </div>
  );
}

export default function SRDPreview({ srdData, serviceUrl, onRunAudit, auditLoading }) {
  const { fields = [], metadata = {}, source, field_count } = srdData;
  const [activeTab, setActiveTab] = useState('fields');

  const pricingLabel =
    metadata.pricing === 'free'
      ? 'Free'
      : Array.isArray(metadata.pricing)
      ? metadata.pricing.join(', ')
      : metadata.pricing;

  const tabs = [
    { id: 'fields', label: `Form Fields (${field_count})` },
    { id: 'workflow', label: 'Workflow' },
    { id: 'pricing', label: 'Pricing' },
  ];

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-slate-700 space-y-4">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-xl font-bold text-slate-100">
              {metadata.service_name ?? 'SRD Extraction Preview'}
            </h2>
            <p className="text-xs text-slate-500 mt-1 font-mono truncate max-w-lg">{source}</p>
          </div>
          <span className="px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-700 text-sm font-bold">
            {field_count} fields extracted
          </span>
        </div>

        {/* Quick-glance cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetaCard label="Workflow" value={metadata.workflow} color="text-indigo-300" />
          <MetaCard label="SLA" value={metadata.sla} color="text-amber-300" />
          <MetaCard
            label="Pricing"
            value={pricingLabel}
            color={metadata.pricing === 'free' ? 'text-emerald-400' : 'text-slate-300'}
          />
          <MetaCard label="Target" value={serviceUrl} color="text-cyan-300" />
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 px-4 pt-2 border-b border-slate-700 bg-slate-900/30">
        {tabs.map((t) => (
          <TabButton key={t.id} label={t.label} active={activeTab === t.id} onClick={() => setActiveTab(t.id)} />
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'fields' && <FieldsTab fields={fields} field_count={field_count} />}
      {activeTab === 'workflow' && <WorkflowTab metadata={metadata} />}
      {activeTab === 'pricing' && <PricingTab metadata={metadata} />}

      {/* Footer */}
      <div className="p-5 border-t border-slate-700 bg-slate-900/50 flex items-center justify-between flex-wrap gap-3">
        <p className="text-sm text-slate-400">
          Review the extracted fields above, then run the live form audit.
        </p>
        <button
          onClick={onRunAudit}
          disabled={auditLoading}
          className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white font-bold py-2.5 px-6 rounded-lg transition-colors text-sm"
        >
          {auditLoading ? '🔍 Scraping live form…' : '▶ Run Full Audit'}
        </button>
      </div>
    </div>
  );
}
