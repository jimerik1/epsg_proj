import React, { useEffect, useState } from 'react';

export default function DocsPage() {
  const [gigs, setGigs] = useState('');
  const [readme, setReadme] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchDoc = async (name, setter) => {
    try {
      const url = `${process.env.REACT_APP_API_URL || 'http://localhost:3001'}/api/docs/text?name=${encodeURIComponent(name)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(await res.text());
      const txt = await res.text();
      setter(txt);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchDoc('gigs', setGigs),
      fetchDoc('readme', setReadme),
    ]).finally(() => setLoading(false));
  }, []);

  const reportUrl = `${process.env.REACT_APP_API_URL || 'http://localhost:3001'}/api/gigs/report/html`;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Project Docs</h3>
      {loading && <div className="text-sm text-gray-600">Loading docs…</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}
      <div className="card">
        <div className="card-header">GIGS HTML Report</div>
        <div className="card-body">
          <iframe title="GIGS Report" src={reportUrl} className="w-full h-[60vh] rounded border" />
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <section className="card">
          <div className="card-header">docs/gigs.md</div>
          <div className="card-body">
            <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded overflow-auto max-h-[60vh]">{gigs}</pre>
          </div>
        </section>
        <section className="card">
          <div className="card-header">README.md</div>
          <div className="card-body">
            <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded overflow-auto max-h-[60vh]">{readme}</pre>
          </div>
        </section>
      </div>
    </div>
  );
}

