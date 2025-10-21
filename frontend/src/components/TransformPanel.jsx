import React, { useState } from 'react';
import { transformDirect, getAvailablePaths } from '../services/api';

export default function TransformPanel() {
  const [source, setSource] = useState('EPSG:4326');
  const [target, setTarget] = useState('EPSG:32631');
  const [lon, setLon] = useState(2.2945);
  const [lat, setLat] = useState(48.8584);
  const [result, setResult] = useState(null);
  const [paths, setPaths] = useState([]);
  const [loading, setLoading] = useState(false);

  const runTransform = async () => {
    setLoading(true);
    try {
      const res = await transformDirect({
        source_crs: source,
        target_crs: target,
        position: { lon: Number(lon), lat: Number(lat) }
      });
      setResult(res);
      const p = await getAvailablePaths(source, target);
      setPaths(p.transformation_paths || []);
    } catch (e) {
      setResult({ error: String(e) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <label>Source CRS: <input value={source} onChange={e => setSource(e.target.value)} /></label>
        <label>Target CRS: <input value={target} onChange={e => setTarget(e.target.value)} /></label>
        <label>Lon: <input type="number" value={lon} onChange={e => setLon(e.target.value)} /></label>
        <label>Lat: <input type="number" value={lat} onChange={e => setLat(e.target.value)} /></label>
        <button onClick={runTransform} disabled={loading}>{loading ? 'Transforming...' : 'Transform'}</button>
      </div>
      {result && (
        <pre style={{ background: '#f8f8f8', padding: 8, marginTop: 12 }}>{JSON.stringify(result, null, 2)}</pre>
      )}
      {paths?.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h4>Available Paths</h4>
          <ul>
            {paths.map(p => (
              <li key={p.path_id}>{p.description} | accuracy: {String(p.accuracy)}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

