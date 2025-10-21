import React from 'react';

export default function AccuracyDisplay({ accuracy }) {
  if (accuracy == null) return <span>Accuracy: unknown</span>;
  return <span>Accuracy: ±{accuracy} m</span>;
}

