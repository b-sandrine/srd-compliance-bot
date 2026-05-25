import React, { useState } from 'react';

export default function FormSubmission({ onParseSRD, loading }) {
  const [serviceUrl, setServiceUrl] = useState('');
  const [srdUrl, setSrdUrl] = useState('');
  const [srdFile, setSrdFile] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    onParseSRD(serviceUrl, srdUrl || null, srdFile || null);
  };

  const clearFile = () => {
    setSrdFile(null);
    // Reset the file input element
    const el = document.getElementById('srd-file-input');
    if (el) el.value = '';
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-xl space-y-6"
    >
      {/* Step indicator */}
      <div className="flex items-center gap-2 text-xs text-slate-500 font-semibold uppercase tracking-widest">
        <span className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px]">1</span>
        Configure Sources
      </div>

      {/* Service URL */}
      <div>
        <label className="block text-sm font-semibold mb-1.5 text-slate-300">
          Production Service URL
        </label>
        <input
          type="url"
          required
          value={serviceUrl}
          onChange={(e) => setServiceUrl(e.target.value)}
          placeholder="https://irembo.gov.rw/services/…"
          className="w-full p-3 rounded-lg bg-slate-950 border border-slate-700 focus:outline-none focus:border-indigo-500 text-slate-200 placeholder-slate-600"
        />
        <p className="text-xs text-slate-500 mt-1">
          The live form URL — will be scraped in the audit step.
        </p>
      </div>

      <hr className="border-slate-700" />

      {/* SRD source */}
      <div>
        <label className="block text-sm font-semibold mb-3 text-slate-300">
          SRD Source <span className="text-slate-500 font-normal">(choose one)</span>
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Notion Document URL</label>
            <input
              type="url"
              value={srdUrl}
              onChange={(e) => setSrdUrl(e.target.value)}
              disabled={!!srdFile}
              placeholder="https://notion.so/…"
              className="w-full p-3 rounded-lg bg-slate-950 border border-slate-700 focus:outline-none focus:border-indigo-500 text-slate-200 placeholder-slate-600 disabled:opacity-40"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Or upload a Markdown file (.md)</label>
            <div className="flex items-center gap-2">
              <input
                id="srd-file-input"
                type="file"
                accept=".md"
                onChange={(e) => setSrdFile(e.target.files[0] || null)}
                disabled={!!srdUrl}
                className="flex-1 p-2 rounded-lg bg-slate-950 border border-slate-700 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-indigo-600 file:text-white file:text-xs hover:file:bg-indigo-500 text-slate-400 disabled:opacity-40"
              />
              {srdFile && (
                <button
                  type="button"
                  onClick={clearFile}
                  className="text-slate-500 hover:text-rose-400 text-lg leading-none"
                  title="Clear file"
                >
                  ×
                </button>
              )}
            </div>
            {srdFile && (
              <p className="text-xs text-emerald-400 mt-1 truncate">{srdFile.name}</p>
            )}
          </div>
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || (!srdUrl && !srdFile)}
        className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-bold py-3 px-4 rounded-lg transition-colors"
      >
        {loading ? '⏳ Parsing SRD…' : '📄 Parse SRD & Preview Fields'}
      </button>
    </form>
  );
}
