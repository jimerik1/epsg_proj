import React, { useState } from 'react';
import {
  getCrsInfo,
  getUnits,
  getGridConvergence,
  getScaleFactor,
  transformDirect,
  getCrsParameters,
} from '../services/api';
import InteractiveMap from '../components/InteractiveMap';

export default function CRSInfoPage() {
  const [code, setCode] = useState('EPSG:32631');
  const [datumCode, setDatumCode] = useState('EPSG:4326');
  const [datumLon, setDatumLon] = useState(2.2945);
  const [datumLat, setDatumLat] = useState(48.8584);
  const [projX, setProjX] = useState('');
  const [projY, setProjY] = useState('');
  const [wgsLon, setWgsLon] = useState(2.2945);
  const [wgsLat, setWgsLat] = useState(48.8584);
  const [info, setInfo] = useState(null);
  const [units, setUnits] = useState(null);
  const [factors, setFactors] = useState(null);
  const [mapProjected, setMapProjected] = useState(null);
  const [projParams, setProjParams] = useState(null);
  const [loading, setLoading] = useState(false);
  const [coordBusy, setCoordBusy] = useState(false);
  const [error, setError] = useState(null);

  const numericDatumLon = datumLon === '' ? null : Number(datumLon);
  const numericDatumLat = datumLat === '' ? null : Number(datumLat);
  const numericProjX = projX === '' ? null : Number(projX);
  const numericProjY = projY === '' ? null : Number(projY);

  const resolveBase = (override) => override || datumCode || code;
  const baseGeodetic = resolveBase();
  const hasProjected = info?.is_projected;

  const updateFromDatum = async (lonVal, latVal, overrideBase, overrideProjected) => {
    const base = resolveBase(overrideBase);
    const projectedFlag = overrideProjected !== undefined ? overrideProjected : hasProjected;
    if (
      !base ||
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
      if (projectedFlag) {
        const toProjected = await transformDirect({
          source_crs: base,
          target_crs: code,
          position: { lon: lonVal, lat: latVal },
        });
        const projected = toProjected.map_position || { x: toProjected.x, y: toProjected.y };
        if (projected) {
          setProjX(projected.x != null ? String(projected.x) : '');
          setProjY(projected.y != null ? String(projected.y) : '');
          setMapProjected(projected);
        }
      } else {
        setProjX('');
        setProjY('');
        setMapProjected(null);
      }

      const toWgs = await transformDirect({
        source_crs: base,
        target_crs: 'EPSG:4326',
        position: { lon: lonVal, lat: latVal },
      });
      const wgs = toWgs.map_position || { x: toWgs.x, y: toWgs.y };
      if (wgs) {
        setWgsLon(wgs.x);
        setWgsLat(wgs.y);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setCoordBusy(false);
    }
  };

  const applyDatumValues = () => updateFromDatum(numericDatumLon, numericDatumLat);

  const applyProjectedInputs = async () => {
    if (!hasProjected || numericProjX == null || numericProjY == null) {
      return;
    }
    if (!Number.isFinite(numericProjX) || !Number.isFinite(numericProjY)) {
      setError('Projected coordinates must be numeric');
      return;
    }
    setCoordBusy(true);
    setError(null);
    try {
      const toDatum = await transformDirect({
        source_crs: code,
        target_crs: baseGeodetic,
        position: { x: numericProjX, y: numericProjY },
      });
      const datum = toDatum.map_position || { x: toDatum.x, y: toDatum.y };
      if (datum) {
        setDatumLon(datum.x);
        setDatumLat(datum.y);
        await updateFromDatum(datum.x, datum.y);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setCoordBusy(false);
    }
  };

  const handleMapChange = async ({ lat: mapLat, lon: mapLon }) => {
    setWgsLat(mapLat);
    setWgsLon(mapLon);
    setCoordBusy(true);
    setError(null);
    try {
      const toDatum = await transformDirect({
        source_crs: 'EPSG:4326',
        target_crs: baseGeodetic,
        position: { lon: mapLon, lat: mapLat },
      });
      const datum = toDatum.map_position || { x: toDatum.x, y: toDatum.y };
      if (datum) {
        setDatumLon(datum.x);
        setDatumLat(datum.y);
        await updateFromDatum(datum.x, datum.y);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setCoordBusy(false);
    }
  };

  const fetchAll = async () => {
    const lonVal = Number(datumLon);
    const latVal = Number(datumLat);
    if (!Number.isFinite(lonVal) || !Number.isFinite(latVal)) {
      setError('Latitude/Longitude must be numeric');
      return;
    }
    setLoading(true);
    setError(null);
    setInfo(null);
    setUnits(null);
    setFactors(null);
    try {
      const meta = await getCrsInfo(code);
      setInfo(meta);
      const newDatumCode = meta.geodetic_crs?.code || code;
      setDatumCode(newDatumCode);
      const u = await getUnits(code);
      setUnits(u.units);
      const pp = await getCrsParameters(code);
      setProjParams(pp);

      if (meta.is_projected) {
        const conv = await getGridConvergence(code, lonVal, latVal);
        const sf = await getScaleFactor(code, lonVal, latVal);
        setFactors({ grid_convergence: conv.meridian_convergence, ...sf });
      }

      await updateFromDatum(lonVal, latVal, newDatumCode || code, meta.is_projected);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3>CRS Information</h3>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>EPSG/CRS Code: <input value={code} onChange={e => setCode(e.target.value)} placeholder="EPSG:32631" /></label>
        <button onClick={fetchAll} disabled={loading}>{loading ? 'Loading…' : 'Fetch Info'}</button>
      </div>

      <div style={{ marginTop: 12, padding: 12, border: '1px solid #ddd', borderRadius: 8 }}>
        <strong>Geographic (datum of {code}) {datumCode ? `— ${datumCode}` : ''}</strong>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          <label>Longitude: <input type="number" value={datumLon} onChange={e => setDatumLon(e.target.value)} /></label>
          <label>Latitude: <input type="number" value={datumLat} onChange={e => setDatumLat(e.target.value)} /></label>
          <button onClick={applyDatumValues} disabled={coordBusy || loading}>Apply Datum Lon/Lat</button>
        </div>
      </div>

      {hasProjected && (
        <div style={{ marginTop: 12, padding: 12, border: '1px solid #ddd', borderRadius: 8 }}>
          <strong>Projected ({code})</strong>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <label>X / Easting: <input type="number" value={projX} onChange={e => setProjX(e.target.value)} placeholder="Projected X" /></label>
            <label>Y / Northing: <input type="number" value={projY} onChange={e => setProjY(e.target.value)} placeholder="Projected Y" /></label>
            <button onClick={applyProjectedInputs} disabled={coordBusy || loading}>Apply Projected X/Y</button>
          </div>
        </div>
      )}

      <div style={{ marginTop: 12, padding: 12, border: '1px solid #ddd', borderRadius: 8 }}>
        <strong>Map Preview (WGS84)</strong>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          <label>WGS84 Lon: <input type="number" value={wgsLon} readOnly /></label>
          <label>WGS84 Lat: <input type="number" value={wgsLat} readOnly /></label>
        </div>
      </div>

      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}

      <div style={{ marginTop: 12 }}>
        <InteractiveMap
          lat={wgsLat}
          lon={wgsLon}
          onPositionChange={handleMapChange}
        />
      </div>

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
      {mapProjected && (
        <div style={{ marginTop: 12 }}>
          <h4>Projected Coordinates ({code})</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(mapProjected, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
