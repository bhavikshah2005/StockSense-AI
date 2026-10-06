export function ComingSoonPage({ title }: { title: string }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
        This section is not available yet.
      </p>
    </div>
  );
}
