import { LineChart, ResponsiveContainer } from "recharts";

export function PriceChartPlaceholder() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-medium text-slate-500">Price chart</h2>
      <p className="mt-2 text-sm text-slate-600">
        Historical prices will render here after a market data provider is connected.
      </p>
      <div className="mt-4 h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={[]} />
        </ResponsiveContainer>
      </div>
    </section>
  );
}
