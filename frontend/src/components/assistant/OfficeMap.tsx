import "leaflet/dist/leaflet.css";

import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";

import type { OfficeInfo } from "../../types/assistant";
import { formatDistance } from "./OfficeCard";

// Leaflet resolves its default marker images from CSS paths that Vite rewrites;
// point it at the bundled image URLs instead.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({ iconRetinaUrl: markerIcon2x, iconUrl: markerIcon, shadowUrl: markerShadow });

const HYDERABAD_CENTRE: [number, number] = [17.385, 78.4867];

interface OfficeMapProps {
  offices: OfficeInfo[];
  userPosition?: { latitude: number; longitude: number } | null;
}

function FitToMarkers({ points }: { points: [number, number][] }) {
  const map = useMap();
  // Re-fit only when the set of points changes, not on every parent render.
  const signature = points.map((p) => p.join(",")).join(";");
  useEffect(() => {
    const latest = signature ? signature.split(";").map((p) => p.split(",").map(Number) as [number, number]) : [];
    if (latest.length === 1) map.setView(latest[0], 14);
    else if (latest.length > 1) map.fitBounds(L.latLngBounds(latest), { padding: [32, 32], maxZoom: 15 });
  }, [map, signature]);
  return null;
}

export default function OfficeMap({ offices, userPosition }: OfficeMapProps) {
  const mapped = offices.filter((o) => o.latitude != null && o.longitude != null);
  const points: [number, number][] = mapped.map((o) => [o.latitude as number, o.longitude as number]);
  if (userPosition) points.push([userPosition.latitude, userPosition.longitude]);

  return (
    <div className="h-72 overflow-hidden rounded-xl border border-slate-200" role="region" aria-label="Map of listed offices">
      <MapContainer center={HYDERABAD_CENTRE} zoom={11} scrollWheelZoom={false} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {mapped.map((office) => (
          <Marker key={office.id} position={[office.latitude as number, office.longitude as number]} title={office.name}>
            <Popup>
              <strong>{office.name}</strong>
              {office.address && <div>{office.address}</div>}
              {office.distance_m != null && <div>About {formatDistance(office.distance_m)} away (straight line)</div>}
              {office.coordinates_source && <div className="text-xs">Position: {office.coordinates_source}</div>}
            </Popup>
          </Marker>
        ))}
        {userPosition && (
          <CircleMarker center={[userPosition.latitude, userPosition.longitude]} radius={8} pathOptions={{ color: "#4f46e5" }}>
            <Popup>Your location</Popup>
          </CircleMarker>
        )}
        <FitToMarkers points={points} />
      </MapContainer>
    </div>
  );
}
