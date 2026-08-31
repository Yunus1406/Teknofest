export function Meter({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-ink/60">{label}</span>
        <span className="font-mono text-ink/70">{pct.toFixed(0)}/100</span>
      </div>
      <div className="h-1.5 rounded-full bg-petrol/15">
        <div className="h-1.5 rounded-full bg-petrol" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
