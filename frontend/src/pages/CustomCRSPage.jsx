import React, { useEffect, useMemo, useState } from 'react';
import CustomCRSEditor from '../components/CustomCRSEditor';
import InteractiveMap from '../components/InteractiveMap';
import InfoTooltip from '../components/InfoTooltip';
import { parseCustomCRS, matchCustomCRS, transformDirect, getCrsInfo } from '../services/api';

const DEFAULT_XML = `
<CD_GEO_SYSTEM geo_system_id="UTM" measure_id="121" geo_system_name="Universal Transverse Mercator" />
<CD_GEO_ZONE geo_system_id="UTM" geo_zone_id="UTM-31N" zone_name="Zone 31N (0 E to 6 E)" lat_origin="0.0" lon_origin="3.0" standard_lat0="0.0" scale_factor="0.9996" standard_lat1="0.0" standard_lon0="0.0" standard_lat2="0.0" standard_lon1="0.0" false_easting="500000.0" false_northing="0.0" radius_sphere="0.0" skew_azimuth0="0.0" skew_azimuth1="0.0" proj_type="0" />
<CD_GEO_DATUM geo_datum_id="ED50" datum_name="European 1950 - Mean" geo_ellipsoid_id="INTERNATIONAL" pmshift="0.0" x_shift="-87.0" y_shift="-98.0" z_shift="-121.0" x_rotate="0.0" y_rotate="0.0" z_rotate="0.0" scale_factor="0.0" />
<CD_GEO_ELLIPSOID geo_ellipsoid_id="INTERNATIONAL" name="International 1924" semi_major="6378388.0" first_eccentricity="0.0819918899790292" />
`;

const DEFAULT_BUILDER = {
  system: {
    geo_system_id: 'UTM',
    measure_id: '121',
    geo_system_name: 'Universal Transverse Mercator',
  },
  zone: {
    geo_zone_id: 'UTM-31N',
    zone_name: 'Zone 31N (0 E to 6 E)',
    lat_origin: '0.0',
    lon_origin: '3.0',
    standard_lat0: '0.0',
    standard_lon0: '0.0',
    scale_factor: '0.9996',
    standard_lat1: '0.0',
    standard_lon1: '0.0',
    standard_lat2: '0.0',
    false_easting: '500000.0',
    false_northing: '0.0',
    radius_sphere: '0.0',
    skew_azimuth0: '0.0',
    skew_azimuth1: '0.0',
    proj_type: '0',
  },
  datum: {
    geo_datum_id: 'ED50',
    datum_name: 'European 1950 - Mean',
    geo_ellipsoid_id: 'INTERNATIONAL',
    pmshift: '0.0',
    x_shift: '-87.0',
    y_shift: '-98.0',
    z_shift: '-121.0',
    x_rotate: '0.0',
    y_rotate: '0.0',
    z_rotate: '0.0',
    scale_factor: '0.0',
  },
  ellipsoid: {
    geo_ellipsoid_id: 'INTERNATIONAL',
    name: 'International 1924',
    semi_major: '6378388.0',
    first_eccentricity: '0.0819918899790292',
  },
};

const SYSTEM_FIELD_INFO = {
  geo_system_id: { label: 'System ID', tip: 'Identifier used in the source software for the CRS family.' },
  measure_id: { label: 'Measurement ID', tip: 'Optional code describing the measurement system.' },
  geo_system_name: { label: 'System Name', tip: 'Human-readable name of the geographic system.' },
};

const ZONE_FIELD_INFO = {
  geo_zone_id: { label: 'Zone ID', tip: 'Unique identifier for the projection zone (e.g., UTM zone code).' },
  zone_name: { label: 'Zone Name', tip: 'Descriptive name for the zone covered by the CRS.' },
  lat_origin: { label: 'Latitude of Origin', tip: 'Latitude of natural or false origin (degrees).' },
  lon_origin: { label: 'Longitude of Origin', tip: 'Longitude of natural origin / central meridian (degrees).' },
  standard_lat0: { label: 'Standard Latitude 0', tip: 'Additional standard latitude parameter if present.' },
  standard_lon0: { label: 'Standard Longitude 0', tip: 'Additional standard longitude parameter if present.' },
  scale_factor: { label: 'Scale Factor', tip: 'Projection scale factor at origin (k0).' },
  standard_lat1: { label: 'Standard Latitude 1', tip: 'First standard parallel (for conic projections).' },
  standard_lon1: { label: 'Standard Longitude 1', tip: 'Longitude associated with standard_lat1.' },
  standard_lat2: { label: 'Standard Latitude 2', tip: 'Second standard parallel (for 2SP projections).' },
  false_easting: { label: 'False Easting', tip: 'Offset added to X/easting values to keep them positive.' },
  false_northing: { label: 'False Northing', tip: 'Offset added to Y/northing values to keep them positive.' },
  radius_sphere: { label: 'Sphere Radius', tip: 'Spherical radius if the projection assumes a sphere.' },
  skew_azimuth0: { label: 'Skew Azimuth 0', tip: 'Optional skew/azimuth parameter used by some custom projections.' },
  skew_azimuth1: { label: 'Skew Azimuth 1', tip: 'Optional secondary skew/azimuth parameter.' },
  proj_type: { label: 'Projection Type Code', tip: 'Numeric code describing the projection in the source system.' },
};

const DATUM_FIELD_INFO = {
  geo_datum_id: { label: 'Datum ID', tip: 'Identifier of the datum definition.' },
  datum_name: { label: 'Datum Name', tip: 'Human-readable datum name.' },
  geo_ellipsoid_id: { label: 'Ellipsoid ID', tip: 'Identifier referencing the ellipsoid definition.' },
  pmshift: { label: 'Prime Meridian Shift', tip: 'Offset of the prime meridian relative to Greenwich (arc-seconds).' },
  x_shift: { label: 'X Shift', tip: 'Helmert translation towards WGS84 along X axis (metres).' },
  y_shift: { label: 'Y Shift', tip: 'Helmert translation towards WGS84 along Y axis (metres).' },
  z_shift: { label: 'Z Shift', tip: 'Helmert translation towards WGS84 along Z axis (metres).' },
  x_rotate: { label: 'X Rotation', tip: 'Helmert rotation about X axis (arc-seconds).' },
  y_rotate: { label: 'Y Rotation', tip: 'Helmert rotation about Y axis (arc-seconds).' },
  z_rotate: { label: 'Z Rotation', tip: 'Helmert rotation about Z axis (arc-seconds).' },
  scale_factor: { label: 'Datum Scale', tip: 'Helmert scaling factor (ppm).' },
};

const ELLIPSOID_FIELD_INFO = {
  geo_ellipsoid_id: { label: 'Ellipsoid ID', tip: 'Identifier of the ellipsoid model.' },
  name: { label: 'Ellipsoid Name', tip: 'Human-readable ellipsoid name.' },
  semi_major: { label: 'Semi-major Axis', tip: 'Equatorial radius of the ellipsoid (metres).' },
  first_eccentricity: { label: 'First Eccentricity', tip: 'First eccentricity describing ellipsoid shape.' },
};

const PROJ_FIELD_INFO = {
  proj: { label: '+proj', tip: 'Projection method keyword, e.g. utm, lcc, tmerc.' },
  zone: { label: '+zone', tip: 'Zone number for projections that use it (UTM).' },
  south: { label: '+south', tip: 'Toggle for southern hemisphere UTM zones.' },
  k0: { label: '+k (scale factor)', tip: 'Scale factor at the natural origin (k0).' },
  lon_0: { label: '+lon_0', tip: 'Longitude of natural origin or central meridian (degrees).' },
  lat_0: { label: '+lat_0', tip: 'Latitude of natural origin (degrees).' },
  x_0: { label: '+x_0', tip: 'False easting applied to output coordinates (projection units).' },
  y_0: { label: '+y_0', tip: 'False northing applied to output coordinates.' },
  a: { label: '+a', tip: 'Semi-major axis of the ellipsoid (metres).' },
  f: { label: '+rf', tip: 'Reciprocal flattening of the ellipsoid (1/f).' },
  e: { label: '+e', tip: 'First eccentricity (used if reciprocal flattening is not supplied).' },
};

const getFieldInfo = (table, key) => table[key] || { label: key, tip: `Value for ${key}` };

export default function CustomCRSPage() {
  const [mode, setMode] = useState('viewer');
  const [xml, setXml] = useState(DEFAULT_XML);
  const [parsed, setParsed] = useState(null);
  const [matches, setMatches] = useState(null);
  const topMatch = matches?.matches?.[0];
  const [selectedCode, setSelectedCode] = useState(null);
  const [geodeticCode, setGeodeticCode] = useState(null);
  const [datumLon, setDatumLon] = useState(2.2945);
  const [datumLat, setDatumLat] = useState(48.8584);
  const [projX, setProjX] = useState('');
  const [projY, setProjY] = useState('');
  const [wgsLon, setWgsLon] = useState(2.2945);
  const [wgsLat, setWgsLat] = useState(48.8584);
  const [loading, setLoading] = useState(false);
  const [coordBusy, setCoordBusy] = useState(false);
  const [error, setError] = useState(null);
  const [builder, setBuilder] = useState(DEFAULT_BUILDER);
  const [projBuilder, setProjBuilder] = useState({
    proj: 'utm',
    zone: '31',
    south: false,
    a: '6378388.0',
    f: '', // optional inverse flattening
    e: '0.0819918899790292',
    k0: '0.9996',
    lon_0: '3',
    lat_0: '0',
    x_0: '500000',
    y_0: '0',
  });
  const [projSourceType, setProjSourceType] = useState('geodetic');
  const [projSourceLon, setProjSourceLon] = useState(2.2945);
  const [projSourceLat, setProjSourceLat] = useState(48.8584);
  const [projSourceX, setProjSourceX] = useState('');
  const [projSourceY, setProjSourceY] = useState('');
  const [projTarget, setProjTarget] = useState('EPSG:4326');
  const [projResult, setProjResult] = useState(null);

  const doParse = async () => {
    setLoading(true); setError(null); setMatches(null);
    try {
      const res = await parseCustomCRS(xml);
      setParsed(res);
      try {
        const m = await matchCustomCRS(xml);
        setMatches(m);
        if (m.matches && m.matches.length > 0) {
          setSelectedCode(m.matches[0].epsg_code);
        }
      } catch (e) {
        // keep parsed but show no matches
        setMatches({ matches: [] });
        setSelectedCode(null);
      }
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  };

  const doMatch = async () => {
    setLoading(true); setError(null);
    try {
      const res = await matchCustomCRS(xml);
      setMatches(res);
      if (res.matches && res.matches.length > 0) {
        setSelectedCode(res.matches[0].epsg_code);
      } else {
        setSelectedCode(null);
      }
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (topMatch && !selectedCode) {
      setSelectedCode(topMatch.epsg_code);
    }
  }, [topMatch, selectedCode]);

  useEffect(() => {
    if (!selectedCode) {
      setGeodeticCode(null);
      return;
    }
    (async () => {
      try {
        const info = await getCrsInfo(selectedCode);
        setGeodeticCode(info.geodetic_crs?.code || null);
      } catch (e) {
        setGeodeticCode(null);
      }
    })();
  }, [selectedCode]);

  useEffect(() => {
    if (selectedCode && geodeticCode) {
      updateProjectedFromGeographic(datumLon, datumLat, { suppressError: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCode, geodeticCode]);

  const numericDatumLon = datumLon === '' ? null : Number(datumLon);
  const numericDatumLat = datumLat === '' ? null : Number(datumLat);
  const numericProjX = projX === '' ? null : Number(projX);
  const numericProjY = projY === '' ? null : Number(projY);

  const updateProjectedFromGeographic = async (lonVal, latVal, options = {}) => {
    if (!selectedCode || lonVal == null || latVal == null || !Number.isFinite(lonVal) || !Number.isFinite(latVal)) {
      return;
    }
    setCoordBusy(true);
    if (!options.suppressError) setError(null);
    try {
      let projected = null;
      if (geodeticCode) {
        const resProj = await transformDirect({
          source_crs: geodeticCode,
          target_crs: selectedCode,
          position: { lon: lonVal, lat: latVal },
        });
        projected = resProj.map_position || { x: resProj.x, y: resProj.y };
      }
      if (projected) {
        setProjX(projected.x != null ? String(projected.x) : '');
        setProjY(projected.y != null ? String(projected.y) : '');
      }

      if (geodeticCode && geodeticCode !== 'EPSG:4326') {
        const resWgs = await transformDirect({
          source_crs: geodeticCode,
          target_crs: 'EPSG:4326',
          position: { lon: lonVal, lat: latVal },
        });
        const wgs = resWgs.map_position || { x: resWgs.x, y: resWgs.y };
        if (wgs) {
          setWgsLon(wgs.x);
          setWgsLat(wgs.y);
        }
      } else {
        setWgsLon(lonVal);
        setWgsLat(latVal);
      }
    } catch (e) {
      if (!options.suppressError) setError(String(e));
    } finally {
      setCoordBusy(false);
    }
  };

  const applyProjectedInputs = async () => {
    if (!selectedCode || numericProjX == null || numericProjY == null || !Number.isFinite(numericProjX) || !Number.isFinite(numericProjY)) {
      setError('Projected coordinates must be numeric');
      return;
    }
    setCoordBusy(true);
    setError(null);
    try {
      const resGeo = await transformDirect({
        source_crs: selectedCode,
        target_crs: geodeticCode || 'EPSG:4326',
        position: { x: numericProjX, y: numericProjY },
      });
      const geo = resGeo.map_position || { x: resGeo.x, y: resGeo.y };
      if (geo) {
        setDatumLon(geo.x);
        setDatumLat(geo.y);
        if (geodeticCode && geodeticCode !== 'EPSG:4326') {
          const resWgs = await transformDirect({
            source_crs: geodeticCode,
            target_crs: 'EPSG:4326',
            position: { lon: geo.x, lat: geo.y },
          });
          const wgs = resWgs.map_position || { x: resWgs.x, y: resWgs.y };
          if (wgs) {
            setWgsLon(wgs.x);
            setWgsLat(wgs.y);
          }
        } else {
          setWgsLon(geo.x);
          setWgsLat(geo.y);
        }
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
    if (!geodeticCode) {
      setDatumLat(mapLat);
      setDatumLon(mapLon);
      await updateProjectedFromGeographic(mapLon, mapLat);
      return;
    }
    setCoordBusy(true);
    setError(null);
    try {
      const resDatum = await transformDirect({
        source_crs: 'EPSG:4326',
        target_crs: geodeticCode,
        position: { lon: mapLon, lat: mapLat },
      });
      const datum = resDatum.map_position || { x: resDatum.x, y: resDatum.y };
      if (datum) {
        setDatumLon(datum.x);
        setDatumLat(datum.y);
        await updateProjectedFromGeographic(datum.x, datum.y);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setCoordBusy(false);
    }
  };

  const mapPosition = useMemo(() => ({ lon: wgsLon, lat: wgsLat }), [wgsLon, wgsLat]);

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Custom CRS</h3>
      <div className="flex gap-2">
        <button className={`btn ${mode==='viewer' ? 'btn-primary' : ''}`} onClick={() => setMode('viewer')} disabled={mode === 'viewer'}>Parse & Match</button>
        <button className={`btn ${mode==='builder' ? 'btn-primary' : ''}`} onClick={() => setMode('builder')} disabled={mode === 'builder'}>Build Definition</button>
        <button className={`btn ${mode==='proj' ? 'btn-primary' : ''}`} onClick={() => setMode('proj')} disabled={mode === 'proj'}>Quick PROJ Builder</button>
      </div>

      {mode === 'viewer' && (
        <>
          <p className="text-sm text-gray-700">Paste XML (CD_GEO_SYSTEM, CD_GEO_ZONE, CD_GEO_DATUM, CD_GEO_ELLIPSOID) below to parse and find EPSG matches.</p>
          <CustomCRSEditor value={xml} onChange={setXml} />
          <div className="flex gap-2 mt-2">
            <button className="btn btn-primary" onClick={doParse} disabled={loading || !xml.trim()}>Parse</button>
            <button className="btn" onClick={doMatch} disabled={loading || !xml.trim()}>Find EPSG Matches</button>
          </div>
        </>
      )}

      {mode === 'builder' && (
        <div style={{ display: 'grid', gap: 12 }}>
          <p>Define CRS metadata and generate XML. Values start with a UTM example.</p>
          <section className="card">
            <div className="card-header">System</div>
            <div className="card-body grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              {Object.entries(builder.system).map(([k, v]) => {
                const meta = getFieldInfo(SYSTEM_FIELD_INFO, k);
                return (
                  <InfoTooltip key={k} label={meta.label} tip={meta.tip}>
                    <input className="input" value={v}
                      onChange={e => setBuilder(prev => ({
                        ...prev,
                        system: { ...prev.system, [k]: e.target.value },
                      }))} />
                  </InfoTooltip>
                );
              })}
            </div>
          </section>
          <section className="card">
            <div className="card-header">Zone / Projection</div>
            <div className="card-body grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              {Object.entries(builder.zone).map(([k, v]) => {
                const meta = getFieldInfo(ZONE_FIELD_INFO, k);
                return (
                  <InfoTooltip key={k} label={meta.label} tip={meta.tip}>
                    <input
                      value={v}
                      onChange={e => setBuilder(prev => ({
                        ...prev,
                        zone: { ...prev.zone, [k]: e.target.value },
                      }))}
                      style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #d1d5db' }}
                    />
                  </InfoTooltip>
                );
              })}
            </div>
          </section>
          <section className="card">
            <div className="card-header">Datum</div>
            <div className="card-body grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              {Object.entries(builder.datum).map(([k, v]) => {
                const meta = getFieldInfo(DATUM_FIELD_INFO, k);
                return (
                  <InfoTooltip key={k} label={meta.label} tip={meta.tip}>
                    <input
                      value={v}
                      onChange={e => setBuilder(prev => ({
                        ...prev,
                        datum: { ...prev.datum, [k]: e.target.value },
                      }))}
                      className="input"
                    />
                  </InfoTooltip>
                );
              })}
            </div>
          </section>
          <section className="card">
            <div className="card-header">Ellipsoid</div>
            <div className="card-body grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              {Object.entries(builder.ellipsoid).map(([k, v]) => {
                const meta = getFieldInfo(ELLIPSOID_FIELD_INFO, k);
                return (
                  <InfoTooltip key={k} label={meta.label} tip={meta.tip}>
                    <input
                      value={v}
                      onChange={e => setBuilder(prev => ({
                        ...prev,
                        ellipsoid: { ...prev.ellipsoid, [k]: e.target.value },
                      }))}
                      className="input"
                    />
                  </InfoTooltip>
                );
              })}
            </div>
          </section>
          <button
            onClick={() => {
              const parts = [];
              const sysAttrs = Object.entries(builder.system).map(([k, v]) => `${k}="${v}"`).join(' ');
              parts.push(`<CD_GEO_SYSTEM ${sysAttrs} />`);
              const zoneAttrs = Object.entries(builder.zone).map(([k, v]) => `${k}="${v}"`).join(' ');
              parts.push(`<CD_GEO_ZONE ${zoneAttrs} />`);
              const datumAttrs = Object.entries(builder.datum).map(([k, v]) => `${k}="${v}"`).join(' ');
              parts.push(`<CD_GEO_DATUM ${datumAttrs} />`);
              const ellAttrs = Object.entries(builder.ellipsoid).map(([k, v]) => `${k}="${v}"`).join(' ');
              parts.push(`<CD_GEO_ELLIPSOID ${ellAttrs} />`);
              const nextXml = `${parts.join('\n')}`;
              setXml(nextXml);
              setMode('viewer');
            }}
          >Generate XML & Switch to Parse</button>
          <CustomCRSEditor value={xml} onChange={setXml} />
        </div>
      )}

      {mode === 'proj' && (
        <div style={{ display: 'grid', gap: 12 }}>
          <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
            <h4>Define PROJ Parameters</h4>
            <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              <InfoTooltip label={PROJ_FIELD_INFO.proj.label} tip={PROJ_FIELD_INFO.proj.tip}>
                <input className="input" value={projBuilder.proj} onChange={e => setProjBuilder(prev => ({ ...prev, proj: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.zone.label} tip={PROJ_FIELD_INFO.zone.tip}>
                <input className="input" value={projBuilder.zone} onChange={e => setProjBuilder(prev => ({ ...prev, zone: e.target.value }))} />
              </InfoTooltip>
              <label title={PROJ_FIELD_INFO.south.tip} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="checkbox" checked={projBuilder.south} onChange={e => setProjBuilder(prev => ({ ...prev, south: e.target.checked }))} />
                {PROJ_FIELD_INFO.south.label}
              </label>
              <InfoTooltip label={PROJ_FIELD_INFO.k0.label} tip={PROJ_FIELD_INFO.k0.tip}>
                <input className="input" value={projBuilder.k0} onChange={e => setProjBuilder(prev => ({ ...prev, k0: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.lon_0.label} tip={PROJ_FIELD_INFO.lon_0.tip}>
                <input className="input" value={projBuilder.lon_0} onChange={e => setProjBuilder(prev => ({ ...prev, lon_0: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.lat_0.label} tip={PROJ_FIELD_INFO.lat_0.tip}>
                <input className="input" value={projBuilder.lat_0} onChange={e => setProjBuilder(prev => ({ ...prev, lat_0: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.x_0.label} tip={PROJ_FIELD_INFO.x_0.tip}>
                <input className="input" value={projBuilder.x_0} onChange={e => setProjBuilder(prev => ({ ...prev, x_0: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.y_0.label} tip={PROJ_FIELD_INFO.y_0.tip}>
                <input className="input" value={projBuilder.y_0} onChange={e => setProjBuilder(prev => ({ ...prev, y_0: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.a.label} tip={PROJ_FIELD_INFO.a.tip}>
                <input className="input" value={projBuilder.a} onChange={e => setProjBuilder(prev => ({ ...prev, a: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.f.label} tip={PROJ_FIELD_INFO.f.tip}>
                <input className="input" value={projBuilder.f} onChange={e => setProjBuilder(prev => ({ ...prev, f: e.target.value }))} />
              </InfoTooltip>
              <InfoTooltip label={PROJ_FIELD_INFO.e.label} tip={PROJ_FIELD_INFO.e.tip}>
                <input className="input" value={projBuilder.e} onChange={e => setProjBuilder(prev => ({ ...prev, e: e.target.value }))} />
              </InfoTooltip>
            </div>
            <div style={{ marginTop: 8 }}>
              <strong>Generated PROJ String</strong>
              <pre className="bg-gray-900 text-green-200 text-xs p-3 rounded">{(() => {
                const parts = [`+proj=${projBuilder.proj}`];
                if (projBuilder.zone) parts.push(`+zone=${projBuilder.zone}`);
                if (projBuilder.south) parts.push('+south');
                if (projBuilder.k0) parts.push(`+k=${projBuilder.k0}`);
                if (projBuilder.lon_0) parts.push(`+lon_0=${projBuilder.lon_0}`);
                if (projBuilder.lat_0) parts.push(`+lat_0=${projBuilder.lat_0}`);
                if (projBuilder.x_0) parts.push(`+x_0=${projBuilder.x_0}`);
                if (projBuilder.y_0) parts.push(`+y_0=${projBuilder.y_0}`);
                if (projBuilder.a) parts.push(`+a=${projBuilder.a}`);
                if (projBuilder.f) parts.push(`+rf=${projBuilder.f}`);
                if (projBuilder.e && !projBuilder.f) parts.push(`+e=${projBuilder.e}`);
                parts.push('+towgs84=-87,-98,-121');
                parts.push('+units=m');
                parts.push('+no_defs');
                return parts.join(' ');
              })()}</pre>
            </div>
          </section>

          <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
            <h4>Transform Test</h4>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <label><input type="radio" value="geodetic" checked={projSourceType === 'geodetic'} onChange={() => setProjSourceType('geodetic')} /> Source Lon/Lat (custom geodetic)</label>
              <label><input type="radio" value="projected" checked={projSourceType === 'projected'} onChange={() => setProjSourceType('projected')} /> Source X/Y (custom CRS)</label>
            </div>
            {projSourceType === 'geodetic' ? (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                <label>Lon: <input type="number" value={projSourceLon} onChange={e => setProjSourceLon(e.target.value)} /></label>
                <label>Lat: <input type="number" value={projSourceLat} onChange={e => setProjSourceLat(e.target.value)} /></label>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                <label>X: <input type="number" value={projSourceX} onChange={e => setProjSourceX(e.target.value)} /></label>
                <label>Y: <input type="number" value={projSourceY} onChange={e => setProjSourceY(e.target.value)} /></label>
              </div>
            )}
            <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <label>Target CRS: <input value={projTarget} onChange={e => setProjTarget(e.target.value)} placeholder="EPSG:4326" /></label>
              <button disabled={coordBusy || loading} onClick={async () => {
                setCoordBusy(true);
                setError(null);
                try {
                  const projParts = [`+proj=${projBuilder.proj}`];
                  if (projBuilder.zone) projParts.push(`+zone=${projBuilder.zone}`);
                  if (projBuilder.south) projParts.push('+south');
                  if (projBuilder.k0) projParts.push(`+k=${projBuilder.k0}`);
                  if (projBuilder.lon_0) projParts.push(`+lon_0=${projBuilder.lon_0}`);
                  if (projBuilder.lat_0) projParts.push(`+lat_0=${projBuilder.lat_0}`);
                  if (projBuilder.x_0) projParts.push(`+x_0=${projBuilder.x_0}`);
                  if (projBuilder.y_0) projParts.push(`+y_0=${projBuilder.y_0}`);
                  if (projBuilder.a) projParts.push(`+a=${projBuilder.a}`);
                  if (projBuilder.f) projParts.push(`+rf=${projBuilder.f}`);
                  if (projBuilder.e && !projBuilder.f) projParts.push(`+e=${projBuilder.e}`);
                  projParts.push('+towgs84=-87,-98,-121');
                  projParts.push('+units=m');
                  projParts.push('+no_defs');
                  const customProj = projParts.join(' ');

                  let sourcePosition;
                  if (projSourceType === 'geodetic') {
                    sourcePosition = { lon: Number(projSourceLon), lat: Number(projSourceLat) };
                  } else {
                    sourcePosition = { x: Number(projSourceX), y: Number(projSourceY) };
                  }

                  if (Object.values(sourcePosition).some(v => Number.isNaN(v))) {
                    throw new Error('Source coordinates must be numeric');
                  }

                  const res = await transformDirect({
                    source_crs: projSourceType === 'geodetic' ? customProj : customProj,
                    target_crs: projTarget,
                    position: sourcePosition,
                  });

                  setProjResult({
                    proj: customProj,
                    source: sourcePosition,
                    target: projTarget,
                    result: res,
                  });
                } catch (e) {
                  setError(String(e));
                } finally {
                  setCoordBusy(false);
                }
              }}>Transform</button>
            </div>
            {projResult && (
              <div style={{ marginTop: 8 }}>
                <h5>Result</h5>
                <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(projResult, null, 2)}</pre>
              </div>
            )}
          </section>
        </div>
      )}
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
      {mode === 'viewer' && selectedCode && (
        <div style={{ marginTop: 12 }}>
          <h4>Location Explorer ({selectedCode})</h4>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <label className="label">Geodetic ({geodeticCode || 'unknown'}) Lon
              <input className="input" type="number" value={datumLon} onChange={e => setDatumLon(e.target.value)} />
            </label>
            <label className="label">Lat
              <input className="input" type="number" value={datumLat} onChange={e => setDatumLat(e.target.value)} />
            </label>
            <button className="btn" onClick={() => updateProjectedFromGeographic(numericDatumLon, numericDatumLat)} disabled={coordBusy || loading}>Apply Geodetic</button>
          </div>
          <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <label className="label">Projected ({selectedCode}) X
              <input className="input" type="number" value={projX} onChange={e => setProjX(e.target.value)} placeholder="Projected X" />
            </label>
            <label className="label">Y
              <input className="input" type="number" value={projY} onChange={e => setProjY(e.target.value)} placeholder="Projected Y" />
            </label>
            <button className="btn" onClick={applyProjectedInputs} disabled={coordBusy || loading}>Apply Projected</button>
            <select className="input" value={selectedCode} onChange={e => setSelectedCode(e.target.value)}>
              {matches?.matches?.map(match => (
                <option key={match.epsg_code} value={match.epsg_code}>{match.epsg_code} — {match.name}</option>
              ))}
            </select>
          </div>
          <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <label className="label">WGS84 Lon
              <input className="input" type="number" value={wgsLon} readOnly />
            </label>
            <label className="label">Lat
              <input className="input" type="number" value={wgsLat} readOnly />
            </label>
          </div>
          <div style={{ marginTop: 12 }}>
            <InteractiveMap
              lat={mapPosition.lat}
              lon={mapPosition.lon}
              onPositionChange={handleMapChange}
            />
          </div>
        </div>
      )}
      {matches && (
        <div style={{ marginTop: 12 }}>
          <h4>EPSG Result</h4>
          {matches.matches && matches.matches.length > 0 ? (
            <div>Top match: <strong>{topMatch.epsg_code}</strong> — {topMatch.name} (score {topMatch.score})</div>
          ) : (
            <div>Found no matching EPSG</div>
          )}
        </div>
      )}
      {parsed && (
        <div style={{ marginTop: 12 }}>
          <h4>Parsed</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(parsed, null, 2)}</pre>
        </div>
      )}
      {matches && (
        <div style={{ marginTop: 12 }}>
          <h4>Matches</h4>
          <pre style={{ background: '#f8f8f8', padding: 8 }}>{JSON.stringify(matches, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
