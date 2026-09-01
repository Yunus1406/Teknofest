"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { STAGES } from "@/lib/stages";
import { useCaseStore } from "@/stores/case-store";

/** Sol tarafta 12 aşamalı dikey akış rayı — numaralandırma anlamlı çünkü
 * gerçek bir üretim hattı sırasını temsil ediyor.
 *
 * Faz K.8 (Madde 10) — önceden StageNav'ın "sonraki" butonu devre dışı
 * bırakılsa bile kullanıcı bu sidebar'dan doğrudan ileri bir aşamaya
 * tıklayıp ön koşulları (ör. uyumlu hat seçimi) tamamen ATLAYABİLİYORDU.
 * Artık `requiresEligibleLine` taşıyan bir aşama, `lineEligible` false iken
 * tıklanamaz/kilitli gösterilir. */
export function StageRail() {
  const pathname = usePathname();
  const lineEligible = useCaseStore((s) => s.lineEligible);
  const activeSlug = STAGES.find((s) => pathname?.includes(s.slug))?.slug;
  const activeNo = STAGES.find((s) => s.slug === activeSlug)?.no ?? 1;

  return (
    <nav
      aria-label="12 aşamalı reçete akışı"
      className="stage-rail-scroll sticky top-0 h-screen w-64 shrink-0 overflow-y-auto border-r border-ink/10 bg-white/40 px-3 py-6"
    >
      <div className="mb-6 px-3">
        <p className="font-heading text-sm font-semibold text-petrol">Reçete OS</p>
        <p className="text-xs text-ink/50">Ambalaj Sürdürülebilirlik Optimizasyonu</p>
      </div>
      <ol className="relative space-y-0.5">
        {STAGES.map((stage) => {
          const isActive = stage.slug === activeSlug;
          const isDone = stage.no < activeNo;
          const isLocked = !isActive && !!stage.requiresEligibleLine && !lineEligible;
          if (isLocked) {
            return (
              <li key={stage.slug} className="relative">
                <span
                  className="flex cursor-not-allowed items-start gap-3 rounded-lg px-3 py-2.5 text-sm opacity-50"
                  title="Önce Aşama 4'te uyumlu bir üretim hattı seçilmeli"
                  aria-disabled="true"
                >
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink/10 font-mono text-[11px] font-medium text-ink/40">
                    ⛔
                  </span>
                  <span className="leading-tight text-ink/40">{stage.shortTitle}</span>
                </span>
              </li>
            );
          }
          return (
            <li key={stage.slug} className="relative">
              <Link
                href={`/${stage.slug}`}
                className={`group flex items-start gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  isActive ? "bg-petrol/10" : "hover:bg-ink/5"
                }`}
              >
                <span
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-medium ${
                    isActive
                      ? "bg-petrol text-white"
                      : isDone
                        ? "bg-pcr/20 text-pcr"
                        : "bg-ink/10 text-ink/50"
                  }`}
                >
                  {stage.no}
                </span>
                <span
                  className={`leading-tight ${isActive ? "font-medium text-petrol" : "text-ink/70"}`}
                >
                  {stage.shortTitle}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
