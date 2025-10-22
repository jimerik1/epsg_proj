import React, { useMemo } from 'react';
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const defaultIcon = L.icon({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  shadowSize: [41, 41],
});

function ClickHandler({ onClick }) {
  useMapEvents({
    click(event) {
      if (onClick) {
        onClick({ lat: event.latlng.lat, lon: event.latlng.lng });
      }
    },
  });
  return null;
}

function ViewUpdater({ center }) {
  const map = useMap();
  React.useEffect(() => {
    if (center && Number.isFinite(center.lat) && Number.isFinite(center.lon)) {
      map.setView([center.lat, center.lon]);
    }
  }, [center?.lat, center?.lon, map]);
  return null;
}

export default function InteractiveMap({
  lat,
  lon,
  onPositionChange,
  height = 320,
  zoom = 5,
  allowSelection = true,
}) {
  const center = useMemo(() => {
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      return { lat, lon };
    }
    return { lat: 0, lon: 0 };
  }, [lat, lon]);

  const markerPosition = Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;

  return (
    <div style={{ height, width: '100%', border: '1px solid #d0d0d0', borderRadius: 8, overflow: 'hidden' }}>
      <MapContainer
        center={[center.lat, center.lon]}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom
        maxZoom={18}
      >
        <TileLayer
          attribution="&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {markerPosition && <Marker position={markerPosition} icon={defaultIcon} />}
        <ViewUpdater center={center} />
        {allowSelection && <ClickHandler onClick={onPositionChange} />}
      </MapContainer>
    </div>
  );
}

