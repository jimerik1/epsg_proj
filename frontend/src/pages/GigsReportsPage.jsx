import React, { useEffect, useState } from 'react';
import { getGigsReport, getGigsReportHtmlUrl, runGigsTests, prefetchGrids } from '../services/api';

function StatusBadge({ status }) {
  const s = String(status || '').toLowerCase();
  const color = s === 'pass' ? 'bg-green-100 text-green-800 border-green-300' : s === 'fail' ? 'bg-red-100 text-red-800 border-red-300' : 'bg-gray-100 text-gray-800 border-gray-300';
  return <span className={`inline-block px-2 py-0.5 text-xs rounded border ${color}`}>{status}</span>;
}

export default function GigsReportsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [series, setSeries] = useState('all');
  const [gridChecks, setGridChecks] = useState(null);

  const fetchReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const json = await getGigsReport();
      setData(json);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReport(); }, []);

  useEffect(() => {
    const api = process.env.REACT_APP_API_URL || 'http://localhost:3001';
    (async () => {
      try {
        const urls = [
          `${api}/api/transform/required-grids?source_crs=EPSG:4258&target_crs=EPSG:27700`,
          `${api}/api/transform/required-grids?source_crs=EPSG:4326&target_crs=EPSG:27700`,
        ];
        const results = await Promise.all(urls.map(u => fetch(u).then(r => r.ok ? r.json() : null).catch(()=>null)));
        setGridChecks(results);
      } catch (e) {
        setGridChecks(null);
      }
    })();
  }, []);

  const fetchMissingGrids = async () => {
    if (!gridChecks) return;
    const names = [];
    for (const gc of gridChecks) {
      if (!gc || !gc.paths) continue;
      const first = gc.paths[0];
      if (first && first.grids) {
        first.grids.forEach(g => { if (!g.present) names.push(g.name); });
      }
    }
    if (!names.length) return;
    try {
      await prefetchGrids(names);
      // re-check
      const api = process.env.REACT_APP_API_URL || 'http://localhost:3001';
      const urls = [
        `${api}/api/transform/required-grids?source_crs=EPSG:4258&target_crs=EPSG:27700`,
        `${api}/api/transform/required-grids?source_crs=EPSG:4326&target_crs=EPSG:27700`,
      ];
      const results = await Promise.all(urls.map(u => fetch(u).then(r => r.ok ? r.json() : null).catch(()=>null)));
      setGridChecks(results);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('prefetchGrids error', e);
    }
  };

  const seriesSummaries = {
    all: 'All series combined. Use the tabs to view a specific test series.',
    '2200': 'Predefined geodetic CRS definitions and metadata checks.',
    '3200': 'User-defined geodetic data objects (parse and construction).',
    '5100': 'Map projection conversions (forward/reverse).',
    '5200': 'Coordinate transformations (Helmert, Molodensky, grid-based, rotations, etc.).',
    '5300': '2D seismic line coordinates and local offset comparisons.',
    '5400': '3D seismic volume coordinates and local offset comparisons.',
    '5500': 'Wells: trajectory and local offset comparisons.',
    '7000': 'Deprecation and audit evidence.'
  };

  const seriesOptions = React.useMemo(() => {
    const s = new Set((data?.tests || []).map(t => String(t.series)));
    const list = Array.from(s).sort();
    return ['all', ...list];
  }, [data]);

  const filteredTests = React.useMemo(() => {
    if (!data?.tests) return [];
    return data.tests.filter(t => series === 'all' || String(t.series) === String(series));
  }, [data, series]);

  const totals = React.useMemo(() => {
    const counts = { pass: 0, fail: 0, skip: 0 };
    for (const t of filteredTests) counts[String(t.status).toLowerCase()] = (counts[String(t.status).toLowerCase()] || 0) + 1;
    return counts;
  }, [filteredTests]);

  const htmlUrl = getGigsReportHtmlUrl();

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">GIGS Test Reports</h3>
      {loading && <div className="text-sm text-gray-600">Loading latest report…</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      {data && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <span>Summary</span>
            <a className="btn" href="#docs" title="Open Docs → GIGS Report">Docs</a>
          </div>
          <div className="card-body space-y-3 text-sm">
            {gridChecks && (
              <div className="border rounded p-2">
                <div className="font-semibold mb-1">Grid checklist</div>
                {gridChecks.map((gc, i) => (
                  <div key={i} className="mb-1">
                    <div className="text-gray-700">{gc ? `${gc.source_crs} → ${gc.target_crs}` : 'n/a'}</div>
                    {gc && gc.paths && gc.paths.length > 0 ? (
                      <ul className="ml-4 list-disc">
                        {gc.paths.slice(0, 1).map(p => (
                          <li key={p.path_id}>
                            {p.description} — grids: {p.grids && p.grids.length ? p.grids.map(g => `${g.name} ${g.present ? '✓' : '✗'}`).join(', ') : 'none'}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="text-gray-500">No paths reported</div>
                    )}
                  </div>
                ))}
                <button className="btn" onClick={fetchMissingGrids}>Fetch missing grids</button>
              </div>
            )}
            <div className="flex gap-6"><div>Generated: <span className="font-medium">{data.generated}</span></div></div>
            <div className="flex flex-wrap items-center gap-2">
              {seriesOptions.map(s => (
                <button key={s} className={`btn ${series===s ? 'btn-primary' : ''}`} onClick={() => setSeries(s)}>{s === 'all' ? 'All' : `Series ${s}`}</button>
              ))}
              <div className="grow" />
              <button className="btn" onClick={fetchReport} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
              <button className="btn btn-primary" onClick={async () => { setRunning(true); try { await runGigsTests(); await fetchReport(); } catch (e) { setError(String(e)); } finally { setRunning(false); } }} disabled={running}>{running ? 'Running…' : 'Run Tests'}</button>
            </div>
            <div className="text-gray-700">{seriesSummaries[series] || ''}</div>
            <div className="flex gap-3">
              <div>Pass: <span className="font-medium text-green-700">{totals.pass}</span></div>
              <div>Fail: <span className="font-medium text-red-700">{totals.fail}</span></div>
              <div>Skip: <span className="font-medium text-gray-700">{totals.skip}</span></div>
            </div>
          </div>
        </div>
      )}

      {filteredTests?.length > 0 && (
        <div className="card">
          <div className="card-header">Tests</div>
          <div className="card-body overflow-auto">
            <div className="mb-2 flex gap-2">
              <button className="btn" onClick={() => exportCsv(filteredTests)}>Export CSV</button>
            </div>
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-4">Series</th>
                  <th className="py-2 pr-4">ID</th>
                  <th className="py-2 pr-4">Description</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Message</th>
                  <th className="py-2 pr-4">Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredTests.map((t, idx) => (
                  <tr key={idx} className="border-b last:border-0">
                    <td className="py-2 pr-4">{t.series}</td>
                    <td className="py-2 pr-4">{t.id}</td>
                    <td className="py-2 pr-4">{t.description}</td>
                    <td className="py-2 pr-4"><StatusBadge status={t.status} /></td>
                    <td className="py-2 pr-4"><span className="text-gray-700">{t.message}</span></td>
                    <td className="py-2 pr-4"><button className="btn" onClick={() => setData(d => ({...d, _selected: t}))}>View</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data?._selected && (
        <TestDetailsModal test={data._selected} onClose={() => setData(d => ({...d, _selected: null}))} />)
      }
    </div>
  );
}

function CodeBlock({ value }) {
  return <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded overflow-auto max-h-64">{JSON.stringify(value, null, 2)}</pre>;
}

function TabButton({ active, onClick, children }) {
  return <button className={`btn ${active ? 'btn-primary' : ''}`} onClick={onClick}>{children}</button>;
}

function TestDetailsModal({ test, onClose }) {
  const [tab, setTab] = React.useState('summary');
  const details = test?.details || {};
  const cases = Array.isArray(details?.cases) ? details.cases : [];
  const [caseFilter, setCaseFilter] = React.useState('all');
  const tolerances = details?.tolerances || {};
  const tolCartesian = Number(tolerances.cartesian_m ?? tolerances.cartesian ?? NaN);
  const tolGeo = Number(tolerances.geographic_deg ?? NaN);
  const points = React.useMemo(() => {
    const set = new Set();
    for (const c of cases) if (c.point) set.add(String(c.point));
    return ['all', ...Array.from(set).sort()];
  }, [cases]);
  const visibleCases = React.useMemo(() => cases.filter(c => caseFilter==='all' || String(c.point) === caseFilter), [cases, caseFilter]);

  const fmtTol = (key, value) => {
    if (value == null) return null;
    const m = ['cartesian_m','round_trip_cartesian_m'];
    const deg = ['geographic_deg','round_trip_geographic_deg'];
    if (m.includes(key)) return `${value} m`;
    if (deg.includes(key)) return `${value} deg`;
    return String(value);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl w-[95vw] max-w-5xl max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div>
            <div className="text-sm text-gray-500">Series {test.series} — {test.id}</div>
            <div className="font-semibold">{test.description} <span className="ml-2"><StatusBadge status={test.status} /></span></div>
          </div>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
        <div className="px-4 py-3 border-b flex gap-2 items-center flex-wrap">
          <TabButton active={tab==='summary'} onClick={() => setTab('summary')}>Summary</TabButton>
          <TabButton active={tab==='cases'} onClick={() => setTab('cases')}>Cases</TabButton>
          <TabButton active={tab==='raw'} onClick={() => setTab('raw')}>Raw JSON</TabButton>
          {tab==='cases' && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-sm text-gray-600">Filter case:</span>
              <select className="input" value={caseFilter} onChange={e => setCaseFilter(e.target.value)}>
                {points.map(p => <option key={p} value={p}>{p === 'all' ? 'All' : p}</option>)}
              </select>
            </div>
          )}
        </div>
        <div className="p-4 overflow-auto max-h-[70vh]">
          {tab === 'summary' && (
            <div className="space-y-3 text-sm">
              <div className="text-gray-700">{test.message}</div>
              <div>
                <div className="font-semibold mb-1">Tolerances</div>
                {Object.keys(tolerances).length ? (
                  <table className="min-w-[320px] text-sm">
                    <tbody>
                      {Object.entries(tolerances).map(([k,v]) => (
                        <tr key={k}><td className="pr-4 py-0.5 text-gray-600">{k.replaceAll('_',' ')}</td><td className="py-0.5 font-medium">{String(v)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                ) : <div className="text-gray-500">No tolerance info.</div>}
              </div>
            </div>
          )}
          {tab === 'cases' && (
            <div className="space-y-3">
              {!visibleCases.length && <div className="text-sm text-gray-600">No case breakdown recorded.</div>}
              {visibleCases.map((c, i) => {
                const d = c.delta || {};
                const dAxis = typeof d.d === 'number' ? d.d : NaN;
                const dLon = typeof d.d_lon === 'number' ? d.d_lon : NaN;
                const dLat = typeof d.d_lat === 'number' ? d.d_lat : NaN;
                const dTvd = typeof d.d_tvd === 'number' ? d.d_tvd : NaN;
                const overCartesian = Number.isFinite(tolCartesian) && Number.isFinite(dAxis) && Math.abs(dAxis) > tolCartesian;
                const overGeo = Number.isFinite(tolGeo) && ((Number.isFinite(dLon) && Math.abs(dLon) > tolGeo) || (Number.isFinite(dLat) && Math.abs(dLat) > tolGeo));
                const badge = (txt) => <span className="ml-2 inline-block px-2 py-0.5 text-xs rounded border bg-red-100 text-red-800 border-red-300">{txt}</span>;
                return (
                <div key={i} className="border rounded-md p-3">
                  <div className="flex items-center justify-between">
                    <div className="text-sm">
                      <span className="font-medium">Point</span>: {String(c.point || '')}
                      <span className="ml-3 font-medium">Direction</span>: {String(c.direction || '')}
                      <span className="ml-3"><StatusBadge status={c.status} /></span>
                      {overCartesian && badge('Δ cartesian > tol')}
                      {overGeo && badge('Δ geographic > tol')}
                      {Number.isFinite(dTvd) && Number.isFinite(tolCartesian) && Math.abs(dTvd) > tolCartesian && badge('Δ TVD > tol')}
                    </div>
                    <button className="btn" onClick={() => openInVia(c)}>Open in Transform Via</button>
                  </div>
                  <div className="grid md:grid-cols-2 gap-3 mt-2 text-sm">
                    <div>
                      <div className="font-semibold">Endpoint</div>
                      <div className="text-gray-700">{c.endpoint || '/api/transform/direct'}</div>
                    </div>
                    <div>
                      <div className="font-semibold">CRS Path</div>
                      <div className="text-gray-700">{c.source_crs} → {c.target_crs}</div>
                    </div>
                  </div>
                  <div className="grid md:grid-cols-2 gap-3 mt-2 text-sm">
                    <div>
                      <div className="font-semibold">Path selection</div>
                      <div className="text-gray-700">hint: {c.path_hint || 'best_available'}{c.path_id != null ? `, path_id: ${c.path_id}` : ''}</div>
                    </div>
                  </div>
                  <div className="mt-2 grid md:grid-cols-2 gap-3">
                    <div>
                      <div className="font-semibold">Payload</div>
                      <CodeBlock value={c.payload} />
                    </div>
                    <div>
                      <div className="font-semibold">Delta</div>
                      <CodeBlock value={c.delta} />
                    </div>
                  </div>
                  <div className="mt-2 grid md:grid-cols-2 gap-3">
                    <div>
                      <div className="font-semibold">Expected</div>
                      <CodeBlock value={c.expected} />
                    </div>
                    <div>
                      <div className="font-semibold">Actual</div>
                      <CodeBlock value={c.actual} />
                    </div>
                  </div>
                </div>
              )})}
            </div>
          )}
          {tab === 'raw' && (
            <CodeBlock value={test} />
          )}
        </div>
      </div>
    </div>
  );
}

function exportCsv(tests) {
  const cols = ['series','id','description','status','message'];
  const header = cols.join(',');
  const rows = tests.map(t => cols.map(k => JSON.stringify(t[k] ?? '')).join(','));
  const csv = [header, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'gigs_report.csv';
  a.click();
  URL.revokeObjectURL(url);
}

function openInVia(caseRow) {
  try {
    const payload = caseRow?.payload || {};
    let path = [];
    let segment_path_ids = undefined;
    if (Array.isArray(payload.path)) {
      path = payload.path;
      if (Array.isArray(payload.segment_path_ids)) segment_path_ids = payload.segment_path_ids;
    } else if (caseRow?.source_crs && caseRow?.target_crs) {
      path = [caseRow.source_crs, caseRow.target_crs];
    }
    const position = payload.position || {};
    const prefill = { path, position };
    if (segment_path_ids) prefill.segment_path_ids = segment_path_ids;
    localStorage.setItem('prefillVia', JSON.stringify(prefill));
    window.location.hash = '#via';
  } catch (e) {
    console.error('openInVia error', e);
  }
}
