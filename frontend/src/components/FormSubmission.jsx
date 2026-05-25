import React, { useState } from 'react';

export default function FormSubmission({ setReportData, setLoading, loading }) {
  const [prodUrl, setProdUrl] = useState('');
  const [srdLink, setSrdLink] = useState('');
  const [srdFile, setSrdFile] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setReportData(null);

    const formData = new FormData();
    formData.append('prod_url', prodUrl);
    if (srdLink) formData.append('srd_link', srdLink);
    if (srdFile) formData.append('srd_file', srdFile);

    try {
      const response = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (response.ok) {
        setReportData(data);
      } else {
        alert(data.detail || 'An error occurred during verification.');
      }
    } catch (err) {
      alert('Cannot connect to compliance backend server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-xl space-y-6">
      <div>
        <label className="block text-sm font-semibold mb-2 text-slate-300">Production Service Environment URL</label>
        <input 
          type="url" required value={prodUrl} onChange={(e) => setProdUrl(e.target.value)}
          placeholder="https://prod.my-app.com/services/form?id=9872"
          className="w-full p-3 rounded-lg bg-slate-950 border border-slate-700 focus:outline-none focus:border-indigo-500 text-slate-200"
        />
      </div>

      <hr className="border-slate-700" />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-semibold mb-2 text-slate-300">Notion SRD Document Link</label>
          <input 
            type="url" value={srdLink} onChange={(e) => setSrdLink(e.target.value)} disabled={!!srdFile}
            placeholder="https://notion.so/workspace/Spec-Page..."
            className="w-full p-3 rounded-lg bg-slate-950 border border-slate-700 focus:outline-none focus:border-indigo-500 text-slate-200 disabled:opacity-50"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold mb-2 text-slate-300">Or Upload Markdown Spec File (`.md`)</label>
          <input 
            type="file" accept=".md" onChange={(e) => setSrdFile(e.target.files[0])} disabled={!!srdLink}
            className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 text-slate-400"
          />
        </div>
      </div>

      <button 
        type="submit" disabled={loading}
        className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3 px-4 rounded-lg transition-colors disabled:bg-slate-700"
      >
        {loading ? '🔍 Activating Scrapers & Parsing Logic...' : 'Run Compliance Audit'}
      </button>
    </form>
  );
}