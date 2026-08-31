export function StatTile({
  label,
  value,
  unit,
  tone = "default",
}: {
  label: string;
  value: string | number;
  unit?: string;
  tone?: "default" | "warn";
}) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink/50">{label}</p>
      <p
        className={`mt-1.5 font-heading text-2xl font-semibold ${tone === "warn" ? "text-warn" : "text-ink"}`}
      >
        {value}
        {unit ? <span className="ml-1 text-base font-normal text-ink/50">{unit}</span> : null}
      </p>
    </div>
  );
}
