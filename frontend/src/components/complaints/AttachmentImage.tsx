import { useEffect, useState } from "react";

import { fetchAttachmentBlob } from "../../services/complaintService";
import type { Attachment } from "../../types/complaint";

/** Loads a protected attachment with the auth header and shows it via an object URL. */
export default function AttachmentImage({ complaintId, attachment }: { complaintId: number; attachment: Attachment }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    fetchAttachmentBlob(complaintId, attachment.id)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [complaintId, attachment.id]);

  if (failed) {
    return (
      <div className="flex aspect-square items-center justify-center rounded-lg border border-dashed border-slate-300 p-2 text-center text-xs text-slate-500">
        Could not load {attachment.original_filename}
      </div>
    );
  }
  if (!url) return <div className="aspect-square animate-pulse rounded-lg bg-slate-100" />;

  return (
    <a href={url} target="_blank" rel="noreferrer" className="group block overflow-hidden rounded-lg border border-slate-200">
      <img src={url} alt={attachment.original_filename} className="aspect-square w-full object-cover transition group-hover:scale-105" />
    </a>
  );
}
