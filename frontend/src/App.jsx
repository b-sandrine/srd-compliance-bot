import React, { useState } from 'react';
import FormSubmission from './components/FormSubmission';
import ReportView from './components/ReportView';

function App() {
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(false);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center py-12 px-4">
      <header className="mb-10 text-center">
        <h1 className="text-4xl font-extrabold text-indigo-400 mb-2">🕵️‍♂️ SRD Compliance Bot</h1>
        <p className="text-slate-400">Automate validation between Spec Sheets and Live Form Implementations</p>
      </header>

      <main className="w-full max-w-4xl space-y-8">
        <FormSubmission setReportData={setReportData} setLoading={setLoading} loading={loading} />
        {reportData && <ReportView report={reportData} />}
      </main>
    </div>
  );
}

export default App;