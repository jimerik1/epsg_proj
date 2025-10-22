import React, { useState } from 'react';

const iconStyle = {
  cursor: 'pointer',
  borderRadius: '50%',
  border: '1px solid currentColor',
  width: 18,
  height: 18,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 11,
  lineHeight: '18px',
  fontFamily: 'system-ui, sans-serif',
};

const bubbleBase = {
  position: 'absolute',
  left: 0,
  top: '100%',
  marginTop: 6,
  minWidth: 220,
  maxWidth: 320,
  padding: '8px 10px',
  borderRadius: 8,
  background: '#1f2937',
  color: '#fff',
  fontSize: 12,
  lineHeight: 1.4,
  boxShadow: '0 8px 20px rgba(15, 23, 42, 0.25)',
  zIndex: 40,
};

export default function InfoTooltip({ label, tip, children, inline = false }) {
  const [open, setOpen] = useState(false);
  return (
    <label
      style={{
        position: 'relative',
        display: inline ? 'inline-flex' : 'flex',
        flexDirection: inline ? 'row' : 'column',
        gap: inline ? 6 : 4,
        fontSize: 14,
        color: '#1f2937',
      }}
      onMouseLeave={() => setOpen(false)}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {label}
        <span
          style={iconStyle}
          onMouseEnter={() => setOpen(true)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          tabIndex={0}
        >
          i
        </span>
      </span>
      {children}
      {open && (
        <span style={bubbleBase}>{tip}</span>
      )}
    </label>
  );
}
