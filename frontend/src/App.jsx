import React, { useState } from 'react';
import CRSInfoPage from './pages/CRSInfoPage';
import TransformPage from './pages/TransformPage';
import CustomCRSPage from './pages/CustomCRSPage';

export default function App() {
  const [page, setPage] = useState('crs');
  return (
    <div style={{ padding: 16, fontFamily: 'system-ui, sans-serif' }}>
      <h2>CRS Transformation Platform</h2>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={() => setPage('crs')} disabled={page==='crs'}>CRS Info</button>
        <button onClick={() => setPage('transform')} disabled={page==='transform'}>Transform</button>
        <button onClick={() => setPage('custom')} disabled={page==='custom'}>Custom CRS</button>
      </div>
      {page === 'crs' && <CRSInfoPage />}
      {page === 'transform' && <TransformPage />}
      {page === 'custom' && <CustomCRSPage />}
    </div>
  );
}
