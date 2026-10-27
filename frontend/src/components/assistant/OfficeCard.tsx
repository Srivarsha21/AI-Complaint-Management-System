import type { ChannelType, OfficeInfo } from "../../types/assistant";

const CHANNEL_LABELS: Record<ChannelType, string> = {
  office: "Office",
  online_portal: "Online portal",
  helpline: "Helpline",
  mobile_app: "Mobile app",
};

export function formatDistance(metres: number): string {
  return metres < 1000 ? `${Math.round(metres / 10) * 10} m` : `${(metres / 1000).toFixed(1)} km`;
}

function formatDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function SourceBadge({ type }: { type: OfficeInfo["source_type"] }) {
  return type === "official" ? (
    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">Official</span>
  ) : (
    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">Third-party</span>
  );
}

/** Office or channel details. Only fields present in the verified record are shown. */
export default function OfficeCard({ office }: { office: OfficeInfo }) {
  const headingId = `office-${office.id}-name`;
  return (
    <article aria-labelledby={headingId} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id={headingId} className="font-semibold text-slate-900">
            {office.name}
          </h3>
          <p className="text-xs text-slate-500">
            {CHANNEL_LABELS[office.channel_type]} · {office.organisation}
          </p>
        </div>
        <SourceBadge type={office.source_type} />
      </div>

      <dl className="mt-3 space-y-1 text-sm">
        {office.address && (
          <div>
            <dt className="sr-only">Address</dt>
            <dd className="text-slate-700">{office.address}</dd>
          </div>
        )}
        {office.distance_m != null && (
          <div>
            <dt className="sr-only">Distance</dt>
            <dd className="text-slate-700">
              About <strong>{formatDistance(office.distance_m)}</strong> away (straight line)
            </dd>
          </div>
        )}
        {office.phone && (
          <div className="flex gap-1">
            <dt className="text-slate-500">Phone:</dt>
            <dd>
              <a className="font-medium text-brand-700 underline" href={`tel:${office.phone.replace(/[^\d+]/g, "")}`}>
                {office.phone}
              </a>
            </dd>
          </div>
        )}
        {office.email && (
          <div className="flex gap-1">
            <dt className="text-slate-500">Email:</dt>
            <dd>
              <a className="text-brand-700 underline" href={`mailto:${office.email}`}>
                {office.email}
              </a>
            </dd>
          </div>
        )}
        {office.website && (
          <div className="flex gap-1">
            <dt className="text-slate-500">Website:</dt>
            <dd className="min-w-0 break-all">
              <a className="text-brand-700 underline" href={office.website} target="_blank" rel="noopener noreferrer">
                {office.website}
              </a>
            </dd>
          </div>
        )}
        {office.notes && <p className="pt-1 text-xs text-slate-500">{office.notes}</p>}
      </dl>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {office.directions_url && (
          <a
            href={office.directions_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
          >
            Directions<span className="sr-only"> to {office.name}</span>
          </a>
        )}
        {office.map_url && (
          <a
            href={office.map_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            View on OpenStreetMap<span className="sr-only"> ({office.name})</span>
          </a>
        )}
      </div>

      <p className="mt-3 text-xs text-slate-500">
        Verified on {formatDate(office.verified_on)} ·{" "}
        <a href={office.source_url} target="_blank" rel="noopener noreferrer" className="underline">
          Source<span className="sr-only"> for {office.name}</span>
        </a>
        {office.coordinates_source && <> · Map position: {office.coordinates_source}</>}
      </p>
    </article>
  );
}
