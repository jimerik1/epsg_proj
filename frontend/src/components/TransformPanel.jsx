import React, { useEffect, useState } from 'react';
import { transformDirect, getAvailablePaths } from '../services/api';
import InteractiveMap from './InteractiveMap';

export default function TransformPanel() {
  const [source, setSource] = useState('EPSG:4326');
  const [target, setTarget] = useState('EPSG:32631');
  const [lon, setLon] = useState(2.2945);
  const [lat, setLat] = useState(48.8584);
  const [x, setX] = useState('');
  const [y, setY] = useState('');
  const [inputMode, setInputMode] = useState('geographic');
  const [result, setResult] = useState(null);
  const [paths, setPaths] = useState([]);
  const [loading, setLoading] = useState(false);
  const [coordBusy, setCoordBusy] = useState(false);
  const [error, setError] = useState(null);

  const numericLon = lon === '' ? null : Number(lon);
  const numericLat = lat === '' ? null : Number(lat);

  const updateProjectedFromGeographic = async (lonVal, latVal) => {
    if (
      !source ||
      lonVal == null ||
      latVal == null ||
      !Number.isFinite(lonVal) ||
      !Number.isFinite(latVal)
    ) {
      return;
    }
    setCoordBusy(true);
    setError(null);
    try {
      const res = await transformDirect({
        source_crs: 'EPSG:4326',
        target_crs: source,
        position: { lon: lonVal, lat: latVal },
      });
      const projected = res.map_position || { x: res.x, y: res.y };
      if (projected) {
        setX(projected.x != null ? String(projected.x) : '');
        setY(projected.y != null ? String(projected.y) : '');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setCoordBusy(false);
    }
  };

  const applyProjectedInputs = async () => {
    if (!source || x === '' || y === '') {
      return;
    }
    const xNum = Number(x);
    const yNum = Number(y);
    if (!Number.isFinite(xNum) || !Number.isFinite(yNum)) {
      setError('Projected coordinates must be numeric');
      return;
    }
    setCoordBusy(true);
    setError(null);
    try {
      const res = await transformDirect({
        source_crs: source,
        target_crs: 'EPSG:4326',
        position: { x: xNum, y: yNum },
      });
      const geo = res.map_position || { x: res.x, y: res.y };
      if (geo) {
        setLon(geo.x);
        setLat(geo.y);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setCoordBusy(false);
    }
  };

  const handleMapChange = async ({ lat: mapLat, lon: mapLon }) => {
    setLat(mapLat);
    setLon(mapLon);
    if (inputMode === 'projected') {
      await updateProjectedFromGeographic(mapLon, mapLat);
    }
  };

  const runTransform = async () => {
    setError(null);
    let position;
    if (inputMode === 'projected') {
      if (x === '' || y === '') {
        setError('Provide both X and Y values');
        return;
      }
      const xVal = Number(x);
      const yVal = Number(y);
      if (!Number.isFinite(xVal) || !Number.isFinite(yVal)) {
        setError('Projected coordinates must be numeric');
        return;
      }
      position = { x: xVal, y: yVal };
    } else {
      if (lon === '' || lat === '') {
        setError('Provide both Lon and Lat values');
        return;
      }
      const lonVal = Number(lon);
      const latVal = Number(lat);
      if (!Number.isFinite(lonVal) || !Number.isFinite(latVal)) {
        setError('Geographic coordinates must be numeric');
        return;
      }
      position = { lon: lonVal, lat: latVal };
    }

    setLoading(true);
    try {
      if (inputMode === 'projected') {
        const toGeo = await transformDirect({
          source_crs: source,
          target_crs: 'EPSG:4326',
          position,
        });
        const geo = toGeo.map_position || { x: toGeo.x, y: toGeo.y };
        if (geo) {
          setLon(geo.x);
          setLat(geo.y);
        }
      } else if (inputMode === 'geographic') {
        await updateProjectedFromGeographic(position.lon, position.lat);
      }

      const res = await transformDirect({
        source_crs: source,
        target_crs: target,
        position,
      });
      setResult(res);
      const p = await getAvailablePaths(source, target);
      setPaths(p.transformation_paths || []);
    } catch (e) {
      setResult({ error: String(e) });
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (inputMode === 'projected') {
      updateProjectedFromGeographic(numericLon, numericLat);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  const handleModeChange = (mode) => {
    setInputMode(mode);
    if (mode === 'projected') {
      updateProjectedFromGeographic(numericLon, numericLat);
    }
  };

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <label>Source CRS: <input value={source} onChange={e => setSource(e.target.value)} /></label>
        <label>Target CRS: <input value={target} onChange={e => setTarget(e.target.value)} /></label>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label><input type="radio" value="geographic" checked={inputMode === 'geographic'} onChange={() => handleModeChange('geographic')} /> Lon/Lat</label>
          <label><input type="radio" value="projected" checked={inputMode === 'projected'} onChange={() => handleModeChange('projected')} /> X/Y (source)</label>
        </div>
        {inputMode === 'geographic' ? (
          <>
            <label>Lon: <input type="number" value={lon} onChange={e => setLon(e.target.value)} /></label>
            <label>Lat: <input type="number" value={lat} onChange={e => setLat(e.target.value)} /></label>
          </>
        ) : (
          <>
            <label>X: <input type="number" value={x} onChange={e => setX(e.target.value)} /></label>
            <label>Y: <input type="number" value={y} onChange={e => setY(e.target.value)} /></label>
            <button onClick={applyProjectedInputs} disabled={coordBusy || loading}>Use X/Y</button>
          </>
        )}
        <button onClick={runTransform} disabled={loading}>{loading ? 'Transforming...' : 'Transform'}</button>
      </div>
      <div style={{ marginTop: 12 }}>
        <InteractiveMap
          lat={numericLat}
          lon={numericLon}
          onPositionChange={handleMapChange}
        />
      </div>
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
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
