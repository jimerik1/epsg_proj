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
    <div>
      <h3>Local Offset Comparison</h3>
      <p>Compare ECEF-based local offsets with grid scale-factor approximation.</p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>Target CRS: <input value={crs} onChange={e => setCrs(e.target.value)} placeholder="EPSG:32040" /></label>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label><input type="radio" checked={refMode === 'geodetic'} onChange={() => setRefMode('geodetic')} /> Geographic</label>
          <label><input type="radio" checked={refMode === 'projected'} onChange={() => setRefMode('projected')} /> Projected</label>
        </div>
      </div>

      {refMode === 'geodetic' ? (
        <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <label>Lon: <input type="number" value={refLon} onChange={e => setRefLon(e.target.value)} /></label>
          <label>Lat: <input type="number" value={refLat} onChange={e => setRefLat(e.target.value)} /></label>
        </div>
      ) : (
        <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <label>X: <input type="number" value={refX} onChange={e => setRefX(e.target.value)} /></label>
          <label>Y: <input type="number" value={refY} onChange={e => setRefY(e.target.value)} /></label>
        </div>
      )}
      <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <label>Height (m): <input type="number" value={refHeight} onChange={e => setRefHeight(e.target.value)} /></label>
        <label>ΔEast (m): <input type="number" value={east} onChange={e => setEast(e.target.value)} /></label>
        <label>ΔNorth (m): <input type="number" value={north} onChange={e => setNorth(e.target.value)} /></label>
        <label>ΔUp (m): <input type="number" value={up} onChange={e => setUp(e.target.value)} /></label>
        <button onClick={handleCompute} disabled={loading}>{loading ? 'Computing…' : 'Compute'}</button>
      </div>

      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}

      <div style={{ marginTop: 12 }}>
        <InteractiveMap
          lat={mapPosition.lat}
          lon={mapPosition.lon}
          onPositionChange={handleMapSelect}
        />
      </div>

      {result && (
        <div style={{ marginTop: 16, display: 'grid', gap: 16 }}>
          <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
            <h4>Reference</h4>
            <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(result.reference, null, 2)}</pre>
          </section>

          <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
            <h4>ECEF Pipeline Result</h4>
            <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(result.ecef_pipeline, null, 2)}</pre>
          </section>

          <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
            <h4>Scale-Factor Approximation</h4>
            {result.scale_factor ? (
              <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(result.scale_factor, null, 2)}</pre>
            ) : (
              <div>No scale-factor result (projection may be geographic or factors unavailable).</div>
            )}
          </section>

          {projectedDiff && (
            <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
              <h4>Projected Coordinate Difference (ECEF − Scale)</h4>
              <div>ΔX: {projectedDiff.dx.toFixed(6)} m</div>
              <div>ΔY: {projectedDiff.dy.toFixed(6)} m</div>
              <div>Planar offset: {projectedDiff.d.toFixed(6)} m</div>
            </section>
          )}

          {geographicDiff && (
            <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
              <h4>Geographic Separation</h4>
              <div>{geographicDiff.d != null ? `${geographicDiff.d.toFixed(3)} m` : 'n/a'}</div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
