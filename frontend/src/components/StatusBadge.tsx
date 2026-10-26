export default function StatusBadge({
  success,
  dryRun,
  reason,
}: {
  success: number;
  dryRun: number;
  reason: string | null;
}) {
  if (success && dryRun) {
    return <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">Dry run</span>;
  }
  if (success) {
    return <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Sent</span>;
  }
  const label = reason?.startsWith("duplicate_") ? "Already applied" : reason || "Failed";
  return <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">{label}</span>;
}
