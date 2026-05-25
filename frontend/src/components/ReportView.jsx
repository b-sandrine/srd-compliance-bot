import React from 'react';

export default function ReportView({ report }) {
  const { compliant, missing_fields, undocumented_fields, logic_mismatches } = report.report;

  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-xl space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Audit Results</h2>
        <span className={`px-4 py-1.5 rounded-full text-sm font-bold ${compliant ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500' : 'bg-rose-500/20 text-rose-400 border border-rose-500'}`}>
          {compliant ? '✓ Compliant with SRD' : '✗ Drift Detected'}
        </span>
      </div>

      {/* Logic Mismatches */}
      {logic_mismatches.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-amber-400 font-semibold text-lg">⚠️ Logic / Hide Expression Drift</h3>
          <div className="overflow-x-auto rounded-lg border border-slate-700">
            <table className="w-full text-left border-collapse bg-slate-950">
              <thead>
                <tr className="bg-slate-900 border-b border-slate-700 text-slate-300 text-sm">
                  <th className="p-3">Field ID</th>
                  <th className="p-3">Expected (SRD)</th>
                  <th className="p-3">Actual (Production)</th>
                </tr>
              </thead>
              <tbody>
                {logic_mismatches.map((mismatch, i) => (
                  <tr key={i} className="border-b border-slate-800 text-sm">
                    <td className="p-3 font-mono text-indigo-300">{mismatch.field_id}</td>
                    <td className="p-3 text-emerald-400 font-mono">{mismatch.expected_logic}</td>
                    <td className="p-3 text-rose-400 font-mono">{mismatch.actual_logic}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Missing Fields */}
      {missing_fields.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-rose-400 font-semibold text-lg">❌ Missing in Production (Defined in SRD)</h3>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {missing_fields.map((field, i) => (
              <li key={i} className="bg-slate-900 p-3 rounded-lg border border-rose-900/30 flex justify-between font-mono text-sm">
                <span className="text-slate-300">{field.field_id}</span>
                <span className="text-slate-500">{field.type}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Undocumented Fields */}
      {undocumented_fields.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-cyan-400 font-semibold text-lg">➕ Undocumented Production Fields (Rogue Elements)</h3>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {undocumented_fields.map((field, i) => (
              <li key={i} className="bg-slate-900 p-3 rounded-lg border border-cyan-900/30 flex justify-between font-mono text-sm">
                <span className="text-slate-300">{field.field_id}</span>
                <span className="text-slate-500">{field.type}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {compliant && (
        <div className="bg-emerald-950/30 border border-emerald-800 p-4 rounded-lg text-emerald-400 text-center font-medium">
          The production configuration flawlessly matches your software requirement document.
        </div>
      )}
    </div>
  );
}