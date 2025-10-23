import React, { useMemo, useState } from 'react';
import InteractiveMap from '../components/InteractiveMap';
import { computeLocalOffset } from '../services/api';

function toNumber(value, fallback = 0) {
  if (value === '' || value === null || value === undefined) return fallback;
  const num = Number(value);
  return Number.isFinite(num) ? num : NaN;
}

function haversineDistance(lon1, lat1, lon2, lat2) {
  if ([lon1, lat1, lon2, lat2].some(v => v == null || Number.isNaN(v))) {
    return null;
  }
  const R = 6371000; // metres
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export default function LocalOffsetPage() {
  const [crs, setCrs] = useState('EPSG:32040');
  const [refMode, setRefMode] = useState('geodetic');
  const [refLon, setRefLon] = useState(-99.2053197);
  const [refLat, setRefLat] = useState(29.3512775);
  const [refX, setRefX] = useState('');
  const [refY, setRefY] = useState('');
  const [refHeight, setRefHeight] = useState(0);
  const [east, setEast] = useState(10);
  const [north, setNorth] = useState(10);
  const [up, setUp] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const mapPosition = useMemo(() => {
    if (result?.ecef_pipeline?.wgs84) {
      return {
        lon: result.ecef_pipeline.wgs84.lon,
        lat: result.ecef_pipeline.wgs84.lat,
      };
    }
    if (refMode === 'geodetic' && Number.isFinite(Number(refLon)) && Number.isFinite(Number(refLat))) {
      return { lon: Number(refLon), lat: Number(refLat) };
    }
    return { lon: 0, lat: 0 };
  }, [refLon, refLat, refMode, result]);

  const handleCompute = async () => {
    setError(null);
    const payload = {
      crs,
      reference: {},
      offset: {},
    };

    if (refMode === 'geodetic') {
      const lonNum = toNumber(refLon, null);
      const latNum = toNumber(refLat, null);
      if (lonNum == null || latNum == null || Number.isNaN(lonNum) || Number.isNaN(latNum)) {
        setError('Longitude and latitude must be numeric');
        return;
      }
      payload.reference.lon = lonNum;
      payload.reference.lat = latNum;
    } else {
      const xNum = toNumber(refX, null);
      const yNum = toNumber(refY, null);
      if (xNum == null || yNum == null || Number.isNaN(xNum) || Number.isNaN(yNum)) {
        setError('Projected X and Y must be numeric');
        return;
      }
      payload.reference.x = xNum;
      payload.reference.y = yNum;
    }

    const heightNum = toNumber(refHeight, 0);
    if (!Number.isFinite(heightNum)) {
      setError('Height must be numeric');
      return;
    }
    payload.reference.height = heightNum;

    const eastNum = toNumber(east, null);
    const northNum = toNumber(north, null);
    const upNum = toNumber(up, 0);
    if ([eastNum, northNum, upNum].some(v => v == null || Number.isNaN(v))) {
      setError('Offsets must be numeric');
      return;
    }
    payload.offset = { east: eastNum, north: northNum, up: upNum };

    setLoading(true);
    try {
      const response = await computeLocalOffset(payload);
      setResult(response);
      if (response.reference?.geodetic) {
        setRefLon(response.reference.geodetic.lon);
        setRefLat(response.reference.geodetic.lat);
      }
      if (response.reference?.projected) {
        setRefX(response.reference.projected.x);
        setRefY(response.reference.projected.y);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleMapSelect = async ({ lat, lon }) => {
    setRefMode('geodetic');
    setRefLat(lat);
    setRefLon(lon);
  };

  const projectedDiff = useMemo(() => {
    if (!result?.ecef_pipeline?.projected || !result?.scale_factor?.projected) return null;
    const dx = result.ecef_pipeline.projected.x - result.scale_factor.projected.x;
    const dy = result.ecef_pipeline.projected.y - result.scale_factor.projected.y;
    return { dx, dy, d: Math.hypot(dx, dy) };
  }, [result]);

  const geographicDiff = useMemo(() => {
    if (!result?.ecef_pipeline?.wgs84 || !result?.scale_factor?.wgs84) return null;
    const d = haversineDistance(
      result.ecef_pipeline.wgs84.lon,
      result.ecef_pipeline.wgs84.lat,
      result.scale_factor.wgs84.lon,
      result.scale_factor.wgs84.lat,
    );
    return { d };
  }, [result]);

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">Local Offset Comparison</h3>
      <p className="text-sm text-gray-700">Compare ECEF-based local offsets with grid scale-factor approximation.</p>

      <div className="flex flex-wrap items-center gap-3">
        <label className="label">Target CRS
          <input className="input" value={crs} onChange={e => setCrs(e.target.value)} placeholder="EPSG:32040" />
        </label>
        <div className="flex items-center gap-3">
          <label className="label inline-flex items-center gap-2"><input type="radio" checked={refMode === 'geodetic'} onChange={() => setRefMode('geodetic')} /> Geographic</label>
          <label className="label inline-flex items-center gap-2"><input type="radio" checked={refMode === 'projected'} onChange={() => setRefMode('projected')} /> Projected</label>
        </div>
      </div>

      {refMode === 'geodetic' ? (
        <div className="flex flex-wrap gap-3">
          <label className="label">Lon
            <input className="input" type="number" value={refLon} onChange={e => setRefLon(e.target.value)} />
          </label>
          <label className="label">Lat
            <input className="input" type="number" value={refLat} onChange={e => setRefLat(e.target.value)} />
          </label>
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          <label className="label">X
            <input className="input" type="number" value={refX} onChange={e => setRefX(e.target.value)} />
          </label>
          <label className="label">Y
            <input className="input" type="number" value={refY} onChange={e => setRefY(e.target.value)} />
          </label>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <label className="label">Height (m)
          <input className="input" type="number" value={refHeight} onChange={e => setRefHeight(e.target.value)} />
        </label>
        <label className="label">ΔEast (m)
          <input className="input" type="number" value={east} onChange={e => setEast(e.target.value)} />
        </label>
        <label className="label">ΔNorth (m)
          <input className="input" type="number" value={north} onChange={e => setNorth(e.target.value)} />
        </label>
        <label className="label">ΔUp (m)
          <input className="input" type="number" value={up} onChange={e => setUp(e.target.value)} />
        </label>
        <button className="btn btn-primary" onClick={handleCompute} disabled={loading}>{loading ? 'Computing…' : 'Compute'}</button>
      </div>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      <div className="mt-3">
        <InteractiveMap
          lat={mapPosition.lat}
          lon={mapPosition.lon}
          onPositionChange={handleMapSelect}
        />
      </div>

      {result && (
        <div className="mt-4 grid gap-4">
          <section className="card">
            <div className="card-header">Reference</div>
            <div className="card-body">
              <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(result.reference, null, 2)}</pre>
            </div>
          </section>

          <section className="card">
            <div className="card-header">ECEF Pipeline Result</div>
            <div className="card-body">
              <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(result.ecef_pipeline, null, 2)}</pre>
            </div>
          </section>

          <section className="card">
            <div className="card-header">Scale-Factor Approximation</div>
            <div className="card-body">
              {result.scale_factor ? (
                <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{JSON.stringify(result.scale_factor, null, 2)}</pre>
              ) : (
                <div className="text-sm text-gray-600">No scale-factor result (projection may be geographic or factors unavailable).</div>
              )}
            </div>
          </section>

          {projectedDiff && (
            <section className="card">
              <div className="card-header">Projected Coordinate Difference (ECEF − Scale)</div>
              <div className="card-body text-sm">
                <div>ΔX: {projectedDiff.dx.toFixed(6)} m</div>
                <div>ΔY: {projectedDiff.dy.toFixed(6)} m</div>
                <div>Planar offset: {projectedDiff.d.toFixed(6)} m</div>
              </div>
            </section>
          )}

          {geographicDiff && (
            <section className="card">
              <div className="card-header">Geographic Separation</div>
              <div className="card-body text-sm">{geographicDiff.d != null ? `${geographicDiff.d.toFixed(3)} m` : 'n/a'}</div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
