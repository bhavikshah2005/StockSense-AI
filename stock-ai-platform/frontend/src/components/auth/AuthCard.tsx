import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type AuthCardProps = {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function AuthCard({ title, children, footer }: AuthCardProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-medium tracking-wide text-emerald-700 uppercase">StockSense AI</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        <div className="mt-6">{children}</div>
        {footer ? <div className="mt-6 text-sm text-slate-600">{footer}</div> : null}
        <p className="mt-6 text-xs leading-5 text-slate-500">
          StockSense AI is for education and research. Prices, news, and analysis can be delayed or incomplete. Nothing here is a forecast, a guarantee, or a personal recommendation.
        </p>
      </div>
    </div>
  );
}

export function TextField({
  label,
  type,
  value,
  autoComplete,
  onChange,
}: {
  label: string;
  type: string;
  value: string;
  autoComplete: string;
  onChange: (value: string) => void;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <label className="block text-sm font-medium text-slate-700" htmlFor={id}>
      {label}
      <input
        id={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-base text-slate-900 outline-none focus:border-emerald-600"
      />
    </label>
  );
}

export function SubmitButton({ pending, label }: { pending: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
    >
      {pending ? "Please wait…" : label}
    </button>
  );
}

export function FormMessage({ tone, children }: { tone: "error" | "success"; children: ReactNode }) {
  const className =
    tone === "error"
      ? "rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
      : "rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800";
  return <p className={className}>{children}</p>;
}

export function AuthLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="font-medium text-emerald-700">
      {children}
    </Link>
  );
}
