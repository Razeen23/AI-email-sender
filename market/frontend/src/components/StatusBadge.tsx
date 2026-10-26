const styles: Record<string, string> = {
  sent: "bg-emerald-50 text-emerald-700",
  dry_run: "bg-sky-50 text-sky-700",
  skipped_dedup: "bg-amber-50 text-amber-700",
  failed: "bg-rose-50 text-rose-700",
};

const labels: Record<string, string> = {
  sent: "Sent",
  dry_run: "Dry run",
  skipped_dedup: "Duplicate",
  failed: "Failed",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] || "bg-slate-100 text-slate-600"}`}>
      {labels[status] || status}
    </span>
  );
}
