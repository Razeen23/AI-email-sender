import { useEffect, useState } from "react";
import { api } from "../api";

type Props = {
  path: string;
  filename: string;
  onClose: () => void;
};

export default function ResumePreview({ path, filename, onClose }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl = "";
    let cancelled = false;
    setSrc(null);
    setError(null);

    fetch(api.resumeFileUrl(path))
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Could not load the resume PDF.");
        }
        const bytes = await response.arrayBuffer();
        return new Blob([bytes], { type: "application/pdf" });
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setSrc(`${objectUrl}#view=FitH`);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return (
    <div className="fixed inset-0 z-20 flex flex-col bg-slate-950/60 p-3 sm:p-5" onClick={onClose}>
      <div
        className="mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col gap-3 rounded-2xl bg-white p-4 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-0.5">
            <p className="text-xs uppercase tracking-wide text-slate-400">Resume preview</p>
            <h2 className="truncate text-sm font-semibold">{filename}</h2>
          </div>
          <button type="button" onClick={onClose} className="btn-secondary">
            Close
          </button>
        </div>
        {error && <p className="shrink-0 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {!error && !src && <p className="text-sm text-slate-500">Loading preview…</p>}
        {src && (
          <iframe src={src} title={filename} className="min-h-0 w-full flex-1 rounded-xl border border-slate-200 bg-slate-50" />
        )}
      </div>
    </div>
  );
}
