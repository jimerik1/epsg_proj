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

