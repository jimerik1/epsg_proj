import React, { useState } from 'react';
import CustomCRSEditor from '../components/CustomCRSEditor';
import { parseCustomCRS, matchCustomCRS } from '../services/api';

export default function CustomCRSPage() {
  const [xml, setXml] = useState('');
  const [parsed, setParsed] = useState(null);
  const [matches, setMatches] = useState(null);
  const topMatch = matches?.matches?.[0];
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const doParse = async () => {
    setLoading(true); setError(null); setMatches(null);
    try {
      const res = await parseCustomCRS(xml);
      setParsed(res);
      try {
        const m = await matchCustomCRS(xml);
        setMatches(m);
      } catch (e) {
        // keep parsed but show no matches
        setMatches({ matches: [] });
      }
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  };

  const doMatch = async () => {
    setLoading(true); setError(null);
    try {
      const res = await matchCustomCRS(xml);
      setMatches(res);
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <h3>Custom CRS</h3>
      <p>Paste XML (CD_GEO_SYSTEM, CD_GEO_ZONE, CD_GEO_DATUM, CD_GEO_ELLIPSOID) below to parse and find EPSG matches.</p>
      <CustomCRSEditor value={xml} onChange={setXml} />
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button onClick={doParse} disabled={loading || !xml.trim()}>Parse</button>
        <button onClick={doMatch} disabled={loading || !xml.trim()}>Find EPSG Matches</button>
      </div>
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
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
