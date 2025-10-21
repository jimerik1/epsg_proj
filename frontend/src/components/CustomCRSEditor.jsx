import React from 'react';

export default function CustomCRSEditor({ value, onChange }) {
  return (
    <textarea rows={8} style={{ width: '100%' }} value={value} onChange={e => onChange(e.target.value)} placeholder="<CD_GEO_SYSTEM ...>...</CD_GEO_SYSTEM>" />
  );
}

