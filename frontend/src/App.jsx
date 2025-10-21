import React, { useState } from 'react';
import TransformPanel from './components/TransformPanel';

export default function App() {
  return (
    <div style={{ padding: 16, fontFamily: 'system-ui, sans-serif' }}>
      <h2>CRS Transformation Platform</h2>
      <TransformPanel />
    </div>
  );
}

