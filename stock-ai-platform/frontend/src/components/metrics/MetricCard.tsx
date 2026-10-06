export function MetricCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2" title={description}>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-slate-900">{value}</dd>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
    </div>
  );
}
