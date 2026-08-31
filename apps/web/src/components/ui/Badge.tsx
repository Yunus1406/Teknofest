import type { Tone } from "@/lib/labels";

const DOT_COLOR: Record<Tone, string> = {
  petrol: "bg-petrol",
  virgin: "bg-virgin",
  pcr: "bg-pcr",
  regranul: "bg-regranul",
  warn: "bg-warn",
  neutral: "bg-ink/40",
};

const BG_COLOR: Record<Tone, string> = {
  petrol: "bg-petrol/10",
  virgin: "bg-virgin/10",
  pcr: "bg-pcr/10",
  regranul: "bg-regranul/10",
  warn: "bg-warn/10",
  neutral: "bg-ink/5",
};

/** Rozet: kimlik her zaman renkli bir nokta + metin ile birlikte taşınır —
 * metin asla veri rengini giymez (yalnızca renk üzerinden ayrım yapılmaz). */
export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium text-ink ${BG_COLOR[tone]}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT_COLOR[tone]}`} aria-hidden />
      {children}
    </span>
  );
}
