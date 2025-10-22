const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

export async function transformDirect(payload) {
  const res = await fetch(`${API_URL}/api/transform/direct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAvailablePaths(source, target) {
  const url = `${API_URL}/api/transform/available-paths?source_crs=${encodeURIComponent(source)}&target_crs=${encodeURIComponent(target)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getCrsInfo(code) {
  const url = `${API_URL}/api/crs/info?code=${encodeURIComponent(code)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getUnits(code) {
  const url = `${API_URL}/api/crs/units/${encodeURIComponent(code)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getGridConvergence(crs, lon, lat) {
  const res = await fetch(`${API_URL}/api/calculate/grid-convergence`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ crs, lon, lat }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getScaleFactor(crs, lon, lat) {
  const res = await fetch(`${API_URL}/api/calculate/scale-factor`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ crs, lon, lat }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getCrsParameters(code) {
  const url = `${API_URL}/api/crs/parameters?code=${encodeURIComponent(code)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function parseCustomCRS(xml) {
  const res = await fetch(`${API_URL}/api/crs/parse-custom`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ xml }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function matchCustomCRS(xml) {
  const res = await fetch(`${API_URL}/api/crs/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ xml }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function computeLocalOffset(payload) {
  const res = await fetch(`${API_URL}/api/transform/local-offset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function computeLocalTrajectory(payload) {
  const res = await fetch(`${API_URL}/api/transform/local-trajectory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
