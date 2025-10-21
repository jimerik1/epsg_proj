import React, { useState } from 'react';
import { getCrsInfo, getUnits, getGridConvergence, getScaleFactor, transformDirect, getCrsParameters } from '../services/api';

export default function CRSInfoPage() {
  const [code, setCode] = useState('EPSG:32631');
  const [lon, setLon] = useState(2.2945);
  const [lat, setLat] = useState(48.8584);
  const [info, setInfo] = useState(null);
  const [units, setUnits] = useState(null);
  const [factors, setFactors] = useState(null);
  const [mapPos, setMapPos] = useState(null);
  const [projParams, setProjParams] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    setInfo(null);
    setUnits(null);
    setFactors(null);
    try {
      const meta = await getCrsInfo(code);
      setInfo(meta);
      const u = await getUnits(code);
      setUnits(u.units);
      const pp = await getCrsParameters(code);
      setProjParams(pp);
      if (meta.is_projected) {
        const conv = await getGridConvergence(code, Number(lon), Number(lat));
        const sf = await getScaleFactor(code, Number(lon), Number(lat));
        setFactors({ grid_convergence: conv.meridian_convergence, ...sf });
      }
      // Get map position in the selected CRS from lon/lat
      const t = await transformDirect({
        source_crs: 'EPSG:4326',
        target_crs: code,
        position: { lon: Number(lon), lat: Number(lat) },
      });
      setMapPos(t.map_position || { x: t.x, y: t.y });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3>CRS Information</h3>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <label>EPSG/CRS Code: <input value={code} onChange={e => setCode(e.target.value)} placeholder="EPSG:32631" /></label>
        <label>Lon: <input type="number" value={lon} onChange={e => setLon(e.target.value)} /></label>
        <label>Lat: <input type="number" value={lat} onChange={e => setLat(e.target.value)} /></label>
        <button onClick={fetchAll} disabled={loading}>{loading ? 'Loading…' : 'Fetch Info'}</button>
      </div>
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
      {info && (
        <div style={{ marginTop: 12 }}>
          <h4>Metadata</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(info, null, 2)}</pre>
        </div>
      )}
      {units && (
        <div style={{ marginTop: 12 }}>
          <h4>Units</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(units, null, 2)}</pre>
        </div>
      )}
      {factors && (
        <div style={{ marginTop: 12 }}>
          <h4>Grid Convergence & Scale Factor</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(factors, null, 2)}</pre>
        </div>
      )}
      {projParams && (
        <div style={{ marginTop: 12 }}>
          <h4>Projection Parameters</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(projParams, null, 2)}</pre>
        </div>
      )}
      {mapPos && (
        <div style={{ marginTop: 12 }}>
          <h4>Map Position (in {code})</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(mapPos, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
