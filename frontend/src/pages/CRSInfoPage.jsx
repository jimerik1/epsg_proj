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
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">CRS Information</h3>
      <div className="flex flex-wrap items-end gap-3">
        <label className="label">EPSG/CRS Code
          <input className="input" value={code} onChange={e => setCode(e.target.value)} placeholder="EPSG:32631" />
        </label>
        <button className="btn btn-primary" onClick={fetchAll} disabled={loading}>{loading ? 'Loading…' : 'Fetch Info'}</button>
      </div>

      <div className="card">
        <div className="card-body">
          <div className="font-semibold">Geographic (datum of {code}) {datumCode ? `— ${datumCode}` : ''}</div>
          <div className="flex flex-wrap gap-3 mt-2">
            <label className="label">Longitude
              <input className="input" type="number" value={datumLon} onChange={e => setDatumLon(e.target.value)} />
            </label>
            <label className="label">Latitude
              <input className="input" type="number" value={datumLat} onChange={e => setDatumLat(e.target.value)} />
            </label>
            <button className="btn" onClick={applyDatumValues} disabled={coordBusy || loading}>Apply Datum Lon/Lat</button>
          </div>
        </div>
      </div>

      {hasProjected && (
        <div className="card">
          <div className="card-body">
            <div className="font-semibold">Projected ({code})</div>
            <div className="flex flex-wrap gap-3 mt-2">
              <label className="label">X / Easting
                <input className="input" type="number" value={projX} onChange={e => setProjX(e.target.value)} placeholder="Projected X" />
              </label>
              <label className="label">Y / Northing
                <input className="input" type="number" value={projY} onChange={e => setProjY(e.target.value)} placeholder="Projected Y" />
              </label>
              <button className="btn" onClick={applyProjectedInputs} disabled={coordBusy || loading}>Apply Projected X/Y</button>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-body">
          <div className="font-semibold">Map Preview (WGS84)</div>
          <div className="flex flex-wrap gap-3 mt-2">
            <label className="label">WGS84 Lon
              <input className="input" type="number" value={wgsLon} readOnly />
            </label>
            <label className="label">WGS84 Lat
              <input className="input" type="number" value={wgsLat} readOnly />
            </label>
          </div>
        </div>
      </div>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      <div style={{ marginTop: 12 }}>
        <InteractiveMap
          lat={wgsLat}
          lon={wgsLon}
          onPositionChange={handleMapChange}
        />
      </div>

      {info && (
        <div className="card">
          <div className="card-header">Metadata</div>
          <div className="card-body">
            <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(info, null, 2)}</pre>
          </div>
        </div>
      )}
      {units && (
        <div className="card">
          <div className="card-header">Units</div>
          <div className="card-body">
            <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(units, null, 2)}</pre>
          </div>
        </div>
      )}
      {factors && (
        <div className="card">
          <div className="card-header">Grid Convergence & Scale Factor</div>
          <div className="card-body">
            <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(factors, null, 2)}</pre>
          </div>
        </div>
      )}
      {projParams && (
        <div className="card">
          <div className="card-header">Projection Parameters</div>
          <div className="card-body">
            <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(projParams, null, 2)}</pre>
          </div>
        </div>
      )}
      {mapProjected && (
        <div className="card">
          <div className="card-header">Projected Coordinates ({code})</div>
          <div className="card-body">
            <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(mapProjected, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
