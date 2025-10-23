import React, { useMemo, useState } from 'react';
import { getAvailablePathsVia, getAvailablePaths, getViaSuggestions, transformVia, transformDirect } from '../services/api';

export default function ViaTransformPage() {
  const [source, setSource] = useState('EPSG:4326');
  const [viaList, setViaList] = useState(['EPSG:4277']);
  const [target, setTarget] = useState('EPSG:27700');
  const [lon, setLon] = useState(-3.1883);
  const [lat, setLat] = useState(55.9533);
  const [legs, setLegs] = useState([]); // [{ from, to, paths:[], selected:null }]
  const [suggestedVias, setSuggestedVias] = useState([]); // [{code, reason}]
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  React.useEffect(() => {
    // Prefill support from GIGS deep link
    try {
      const raw = localStorage.getItem('prefillVia');
      if (!raw) return;
      localStorage.removeItem('prefillVia');
      const data = JSON.parse(raw);
      if (Array.isArray(data.path) && data.path.length >= 2) {
        setSource(data.path[0] || '');
        setTarget(data.path[data.path.length - 1] || '');
        setViaList(data.path.slice(1, -1));
      }
      const pos = data.position || {};
      if (typeof pos.lon === 'number' && typeof pos.lat === 'number') {
        setLon(pos.lon);
        setLat(pos.lat);
      }
      // Fetch paths and apply any provided segment_path_ids
      (async () => {
        const newLegs = await fetchPaths();
        if (Array.isArray(data.segment_path_ids)) {
          setLegs((ls) => ls.map((l, i) => ({ ...l, selected: data.segment_path_ids[i] ?? l.selected })));
        }
      })();
    } catch (e) {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchPaths = async () => {
    setError(null);
    try {
      // Refresh suggestions for current endpoints
      try {
        const sugg = await getViaSuggestions(source, target);
        setSuggestedVias(sugg.suggestions || []);
      } catch (e) {
        setSuggestedVias([]);
      }
      const crsPath = [source, ...viaList.filter(v => (v || '').trim() !== ''), target];
      const pairs = crsPath.slice(0, -1).map((from, i) => ({ from, to: crsPath[i + 1] }));

      // Fetch available paths per leg (use bulk endpoint for 2-leg for speed, otherwise per pair)
      let legResults = [];
      if (pairs.length === 2) {
        const data = await getAvailablePathsVia(pairs[0].from, pairs[0].to, pairs[1].to);
        legResults = [data.leg1_paths || [], data.leg2_paths || []];
      } else {
        legResults = await Promise.all(
          pairs.map(async (p) => {
            const res = await getAvailablePaths(p.from, p.to);
            return res.transformation_paths || [];
          })
        );
      }

      const toNum = (v) => (v == null || Number(v) < 0 ? Number.POSITIVE_INFINITY : Number(v));
      const newLegs = pairs.map((p, idx) => {
        const options = legResults[idx] || [];
        const best = options.reduce(
          (acc, cur) => {
            const a = toNum(cur.accuracy);
            return a < acc.bestVal ? { bestVal: a, bestId: cur.path_id } : acc;
          },
          { bestVal: Number.POSITIVE_INFINITY, bestId: options.length ? options[0].path_id : null }
        );
        return { from: p.from, to: p.to, paths: options, selected: best.bestId };
      });
      setLegs(newLegs);
    } catch (e) {
      setError(String(e));
    }
  };

  const run = async () => {
    setError(null);
    setBusy(true);
    setResult(null);
    try {
      const position = { lon: Number(lon), lat: Number(lat) };
      // Ensure input numeric
      if (!Number.isFinite(position.lon) || !Number.isFinite(position.lat)) {
        setError('Lon/Lat must be numeric');
        return;
      }
      const path = [source, ...viaList.filter(v => (v || '').trim() !== ''), target];
      const payload = {
        path,
        position,
        segment_path_ids: legs.map(l => (l.selected == null ? null : l.selected)),
      };
      const res = await transformVia(payload);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const quickDirect = async (leg) => {
    // Helper to quickly test a direct leg using the selected path_id
    setError(null);
    setBusy(true);
    setResult(null);
    try {
      const position = { lon: Number(lon), lat: Number(lat) };
      const idx = leg - 1;
      const l = legs[idx];
      const pathId = l?.selected;
      const src = l?.from;
      const dst = l?.to;
      const res = await transformDirect({
        source_crs: src,
        target_crs: dst,
        position,
        path_id: pathId,
      });
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const fmtNumber = (val) => {
    const n = Number(val);
    if (!Number.isFinite(n)) return 'unknown';
    const fixed = (Math.abs(n) >= 1 ? n.toFixed(2) : n.toFixed(3))
      .replace(/\.0+$/,'')
      .replace(/(\.\d*?)0+$/,'$1');
    return fixed;
  };

  const fmtAcc = (p) => {
    if (!p) return 'unknown';
    const val = p.accuracy;
    if (val == null || Number(val) < 0) return 'unknown';
    const unit = p.accuracy_unit || 'm';
    return `${fmtNumber(val)} ${unit}`;
  };

  const fmtOps = (p) => {
    const inf = p?.operations_info || [];
    if (!inf.length) return null;
    const steps = inf.map((s) => {
      const m = s?.method_name || s?.name || 'op';
      const code = s?.authority && s?.code ? `${s.authority}:${s.code}` : null;
      return code ? `${m} [${code}]` : m;
    });
    return steps.join(' + ');
  };

  const routeOptions = useMemo(() => {
    if (legs.length !== 2) return [];
    const leg1 = legs[0]?.paths || [];
    const leg2 = legs[1]?.paths || [];
    const toNum = (v) => (v == null || Number(v) < 0 ? Number.POSITIVE_INFINITY : Number(v));
    const fmt = (p) => fmtAcc(p);
    const arr = [];
    for (const p1 of leg1) {
      for (const p2 of leg2) {
        const accNum = toNum(p1.accuracy) + toNum(p2.accuracy);
        arr.push({
          leg1: p1,
          leg2: p2,
          cumulativeAccuracy: Number.isFinite(accNum) ? accNum : null,
          label: `L1 #${p1.path_id} (acc: ${fmt(p1)}) + L2 #${p2.path_id} (acc: ${fmt(p2)})` ,
        });
      }
    }
    arr.sort((a, b) => {
      const aa = a.cumulativeAccuracy ?? Number.POSITIVE_INFINITY;
      const bb = b.cumulativeAccuracy ?? Number.POSITIVE_INFINITY;
      return aa - bb;
    });
    return arr;
  }, [legs]);

  const selectedCumulativeAccuracy = useMemo(() => {
    if (!legs.length) return null;
    let sum = 0;
    for (const l of legs) {
      const p = (l.paths || []).find(x => x.path_id === l.selected);
      const val = p?.accuracy;
      if (val == null || Number(val) < 0) return null;
      sum += Number(val);
    }
    return Number.isFinite(sum) ? sum : null;
  }, [legs]);

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Transform Via CRS</h3>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        <label className="label">Source
          <input className="input w-full" value={source} onChange={e => setSource(e.target.value)} />
        </label>
        <label className="label">Target
          <input className="input w-full" value={target} onChange={e => setTarget(e.target.value)} />
        </label>
        <div className="flex gap-3">
          <label className="label">Lon
            <input className="input" type="number" value={lon} onChange={e => setLon(e.target.value)} />
          </label>
          <label className="label">Lat
            <input className="input" type="number" value={lat} onChange={e => setLat(e.target.value)} />
          </label>
        </div>
      </div>
      <div className="card">
        <div className="card-header">Via(s)</div>
        <div className="card-body flex flex-wrap items-center gap-2">
          {viaList.map((v, i) => (
            <div key={i} className="flex items-center gap-2">
              <input className="input" value={v} onChange={e => {
                const copy = [...viaList];
                copy[i] = e.target.value;
                setViaList(copy);
              }} />
              {suggestedVias.length > 0 && (
                <select className="input" value="" onChange={(e) => {
                  const val = e.target.value;
                  if (!val) return;
                  const copy = [...viaList];
                  copy[i] = val;
                  setViaList(copy);
                }}>
                  <option value="">suggest…</option>
                  {suggestedVias.map(s => (
                    <option key={s.code} value={s.code}>{s.code} — {s.reason}</option>
                  ))}
                </select>
              )}
              <button className="btn" onClick={() => {
                const copy = viaList.slice();
                copy.splice(i, 1);
                setViaList(copy);
              }} disabled={viaList.length === 0}>Remove</button>
            </div>
          ))}
          <button className="btn" onClick={() => {
            const existing = new Set(viaList.filter(v=>v));
            const pick = (suggestedVias.find(s => !existing.has(s.code)) || {}).code || '';
            setViaList([...viaList, pick]);
          }}>+ Add via</button>
          <div className="grow"></div>
          <button className="btn btn-primary" onClick={fetchPaths}>List Paths</button>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {legs.map((l, idx) => (
          <div key={`${l.from}->${l.to}`} className="card">
            <div className="card-header">Leg {idx + 1}: {l.from} → {l.to}</div>
            {l.paths?.length ? (
              <ul className="card-body space-y-2">
                {l.paths.map(p => (
                  <li key={p.path_id} className="flex items-start gap-2">
                    <label className="flex items-start gap-2">
                      <input type="radio" name={`leg_${idx}`} value={p.path_id}
                        checked={l.selected === p.path_id}
                        onChange={() => {
                          const copy = legs.slice();
                          copy[idx] = { ...copy[idx], selected: p.path_id };
                          setLegs(copy);
                        }} />
                      <span>
                        <span className="font-medium">{p.description}</span>
                        <span className="ml-2 text-sm text-gray-600">(acc: {fmtAcc(p)})</span>
                        {fmtOps(p) && (
                          <div className="text-xs text-gray-500 mt-1">methods: {fmtOps(p)}</div>
                        )}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            ) : <div className="card-body text-sm text-gray-500">No paths listed yet.</div>}
            <div className="card-body pt-0">
              <button className="btn" onClick={() => quickDirect(idx + 1)} disabled={busy || l.selected == null}>Test Leg {idx + 1} Direct</button>
            </div>
          </div>
        ))}
      </div>

      <div className="text-sm text-gray-700">Selected route cumulative accuracy: <span className="font-medium">{selectedCumulativeAccuracy == null ? 'unknown' : `${fmtNumber(selectedCumulativeAccuracy)} m`}</span></div>

      {legs.length > 0 && (
        <div className="card">
          <div className="card-header">Selected route details</div>
          <ul className="card-body space-y-2">
            {legs.map((l, idx) => {
              const p = (l.paths || []).find(x => x.path_id === l.selected);
              return (
                <li key={`sel-${idx}`} className="text-sm">
                  <span className="font-medium">Leg {idx + 1}: {l.from} → {l.to}</span>
                  <span className="ml-2">{p ? p.description : '—'}</span>
                  <span className="ml-2 text-gray-600">(acc: {p ? fmtAcc(p) : 'unknown'})</span>
                  {p && fmtOps(p) && <div className="text-xs text-gray-500">methods: {fmtOps(p)}</div>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {routeOptions.length > 0 && (
        <div className="card">
          <div className="card-header">Route Options (source → via → target)</div>
          <ol className="card-body list-decimal ml-6 space-y-1">
            {routeOptions.map((opt, idx) => (
              <li key={`${opt.leg1.path_id}-${opt.leg2.path_id}`}>
                {opt.label} → cumulative: {opt.cumulativeAccuracy == null ? 'unknown' : `${fmtNumber(opt.cumulativeAccuracy)} m`}
                {idx === 0 ? '  ← best' : ''}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div>
        <button className="btn btn-primary" onClick={run} disabled={busy || !legs.length || legs.some(l => l.selected == null)}>
          {busy ? 'Transforming…' : 'Transform Via'}
        </button>
      </div>

      {error && <div className="text-red-600 text-sm mt-2">{error}</div>}
      {result && (
        <pre className="mt-2 bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(result, null, 2)}</pre>
      )}
    </div>
  );
}
