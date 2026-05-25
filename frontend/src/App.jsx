import React, { useState } from 'react';
import FormSubmission from './components/FormSubmission';
import SRDPreview from './components/SRDPreview';
import ReportView from './components/ReportView';

const API = 'http://localhost:8000';

function StatusBanner({ msg }) {
  if (!msg) return null;
  return (
    <div className="flex items-center gap-2 text-indigo-300 text-sm animate-pulse bg-slate-800 border border-indigo-800 rounded-lg px-4 py-2.5">
      <span className="inline-block w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
      {msg}
    </div>
  );
}

export default function App() {
  // Phase 1 — SRD parsing
  const [srdData, setSrdData] = useState(null);      // parsed SRD result
  const [srdLoading, setSrdLoading] = useState(false);
  const [srdStatus, setSrdStatus] = useState('');

  // Phase 2 — full audit
  const [reportData, setReportData] = useState(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditStatus, setAuditStatus] = useState('');

  // Stored params so SRDPreview can trigger the audit without re-entering inputs
  const [auditParams, setAuditParams] = useState(null); // { serviceUrl, srdUrl, srdFile }

  // ---- Phase 1: parse SRD ------------------------------------------------
  const handleParseSRD = async (serviceUrl, srdUrl, srdFile) => {
    setSrdLoading(true);
    setSrdData(null);
    setReportData(null);
    setSrdStatus('Parsing SRD document…');

    const fd = new FormData();
    if (srdUrl) fd.append('srd_url', srdUrl);
    if (srdFile) fd.append('srd_file', srdFile);

    try {
      const res = await fetch(`${API}/api/parse-srd`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || 'Failed to parse SRD.');
        return;
      }
      setSrdData(data);
      setAuditParams({ serviceUrl, srdUrl, srdFile });
    } catch {
      alert('Cannot reach the backend server.');
    } finally {
      setSrdLoading(false);
      setSrdStatus('');
    }
  };

  // ---- Phase 2: full audit -----------------------------------------------
  const handleRunAudit = async () => {
    if (!auditParams) return;
    const { serviceUrl, srdUrl, srdFile } = auditParams;

    setAuditLoading(true);
    setReportData(null);
    setAuditStatus('Submitting audit job…');

    const fd = new FormData();
    fd.append('service_url', serviceUrl);
    if (srdUrl) fd.append('srd_url', srdUrl);
    if (srdFile) fd.append('srd_file', srdFile);

    try {
      const res = await fetch(`${API}/api/analyze`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || 'Failed to start audit.');
        return;
      }

      const { job_id } = data;
      setAuditStatus('Launching browser & scraping live form…');

      while (true) {
        await new Promise((r) => setTimeout(r, 2500));
        const statusRes = await fetch(`${API}/api/status/${job_id}`);
        const statusData = await statusRes.json();

        if (statusData.status === 'complete') {
          setAuditStatus('Fetching report…');
          const reportRes = await fetch(`${API}/api/report/${job_id}`);
          setReportData(await reportRes.json());
          setAuditStatus('');
          break;
        } else if (statusData.status === 'error') {
          alert(`Audit failed: ${statusData.error}`);
          setAuditStatus('');
          break;
        } else {
          setAuditStatus(`Analysis running — scraping & comparing…`);
        }
      }
    } catch {
      alert('Cannot reach the backend server.');
      setAuditStatus('');
    } finally {
      setAuditLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center py-12 px-4">
      <header className="mb-10 text-center">
        <h1 className="text-4xl font-extrabold text-indigo-400 mb-2">SRD Compliance Bot</h1>
        <p className="text-slate-400">Parse your spec sheet, review extracted fields, then audit the live form.</p>
      </header>

      <main className="w-full max-w-5xl space-y-6">
        {/* Step 1: inputs */}
        <FormSubmission onParseSRD={handleParseSRD} loading={srdLoading} />

        {srdStatus && <StatusBanner msg={srdStatus} />}

        {/* Step 2: SRD preview */}
        {srdData && (
          <>
            {auditStatus && <StatusBanner msg={auditStatus} />}
            <SRDPreview
              srdData={srdData}
              serviceUrl={auditParams?.serviceUrl}
              onRunAudit={handleRunAudit}
              auditLoading={auditLoading}
            />
          </>
        )}

        {/* Step 3: comparison report */}
        {reportData && <ReportView report={reportData} />}
      </main>
    </div>
  );
}
