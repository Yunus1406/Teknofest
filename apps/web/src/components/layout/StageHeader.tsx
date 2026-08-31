export function StageHeader({
  no,
  title,
  description,
}: {
  no: number;
  title: string;
  description: string;
}) {
  return (
    <header className="mb-8">
      <p className="font-mono text-xs font-medium uppercase tracking-widest text-petrol/70">
        Aşama {no}/12
      </p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink md:text-3xl">{title}</h1>
      <p className="mt-2 max-w-2xl text-sm text-ink/60">{description}</p>
    </header>
  );
}
