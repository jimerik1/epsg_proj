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
  const [selectedPathId, setSelectedPathId] = useState(null);
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
        ...(selectedPathId != null ? { path_id: selectedPathId } : {}),
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
    // Refresh available paths on CRS change
    (async () => {
      try {
        const p = await getAvailablePaths(source, target);
        setPaths(p.transformation_paths || []);
        setSelectedPathId(null);
      } catch (e) {
        // ignore
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, target]);

  const handleModeChange = (mode) => {
    setInputMode(mode);
    if (mode === 'projected') {
      updateProjectedFromGeographic(numericLon, numericLat);
    }
  };

  return (
    <div className="card">
      <div className="card-body flex flex-wrap gap-3 items-end">
        <label className="label">Source CRS
          <input className="input" value={source} onChange={e => setSource(e.target.value)} />
        </label>
        <label className="label">Target CRS
          <input className="input" value={target} onChange={e => setTarget(e.target.value)} />
        </label>
        <div className="flex items-center gap-3">
          <label className="label inline-flex items-center gap-2"><input type="radio" value="geographic" checked={inputMode === 'geographic'} onChange={() => handleModeChange('geographic')} /> Lon/Lat</label>
          <label className="label inline-flex items-center gap-2"><input type="radio" value="projected" checked={inputMode === 'projected'} onChange={() => handleModeChange('projected')} /> X/Y (source)</label>
        </div>
        {inputMode === 'geographic' ? (
          <>
            <label className="label">Lon
              <input className="input" type="number" value={lon} onChange={e => setLon(e.target.value)} />
            </label>
            <label className="label">Lat
              <input className="input" type="number" value={lat} onChange={e => setLat(e.target.value)} />
            </label>
          </>
        ) : (
          <>
            <label className="label">X
              <input className="input" type="number" value={x} onChange={e => setX(e.target.value)} />
            </label>
            <label className="label">Y
              <input className="input" type="number" value={y} onChange={e => setY(e.target.value)} />
            </label>
            <button className="btn" onClick={applyProjectedInputs} disabled={coordBusy || loading}>Use X/Y</button>
          </>
        )}
        <button className="btn btn-primary" onClick={runTransform} disabled={loading}>{loading ? 'Transforming...' : 'Transform'}</button>
      </div>
      <div className="px-4 pb-4">
        <InteractiveMap
          lat={numericLat}
          lon={numericLon}
          onPositionChange={handleMapChange}
        />
      </div>
      {error && <div className="text-red-600 text-sm px-4">{error}</div>}
      {result && (
        <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded mx-4 my-3">{JSON.stringify(result, null, 2)}</pre>
      )}
      {paths?.length > 0 && (
        <div className="px-4 pb-4">
          <h4 className="font-semibold mb-1">Available Paths</h4>
          <div className="flex gap-2 items-center flex-wrap">
            <label className="label">Use Path
              <select className="input" value={selectedPathId ?? ''} onChange={e => setSelectedPathId(e.target.value === '' ? null : Number(e.target.value))}>
                <option value="">Best available</option>
                {paths.map(p => (
                  <option key={p.path_id} value={p.path_id}>
                    #{p.path_id} | {p.description} | acc: {p.accuracy == null || Number(p.accuracy) < 0 ? 'unknown' : `${Number(p.accuracy) >= 1 ? Number(p.accuracy).toFixed(2).replace(/\.0+$/,'').replace(/(\.\d*?)0+$/,'$1') : Number(p.accuracy).toFixed(3).replace(/\.0+$/,'').replace(/(\.\d*?)0+$/,'$1')} ${p.accuracy_unit || 'm'}`}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
