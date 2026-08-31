export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`card p-5 ${className}`}>{children}</div>;
}

export function CardTitle({ children, subtitle }: { children: React.ReactNode; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h3 className="font-heading text-lg font-medium text-ink">{children}</h3>
      {subtitle ? <p className="mt-1 text-sm text-ink/60">{subtitle}</p> : null}
    </div>
  );
}
