import React from 'react';

export default function CRSSelector({ value, onChange }) {
  return (
    <input value={value} onChange={e => onChange(e.target.value)} placeholder="EPSG:4326" />
  );
}

