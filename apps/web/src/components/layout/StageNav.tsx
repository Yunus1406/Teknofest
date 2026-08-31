"use client";

import Link from "next/link";
import { STAGES } from "@/lib/stages";
import { Button } from "@/components/ui/Button";

export function StageNav({ currentNo, nextEnabled = true }: { currentNo: number; nextEnabled?: boolean }) {
  const prev = STAGES.find((s) => s.no === currentNo - 1);
  const next = STAGES.find((s) => s.no === currentNo + 1);
  return (
    <div className="mt-10 flex items-center justify-between border-t border-ink/10 pt-6">
      {prev ? (
        <Link href={`/${prev.slug}`}>
          <Button variant="ghost">← {prev.shortTitle}</Button>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link href={nextEnabled ? `/${next.slug}` : "#"} aria-disabled={!nextEnabled}>
          <Button variant="primary" disabled={!nextEnabled}>
            {next.shortTitle} →
          </Button>
        </Link>
      ) : (
        <span />
      )}
    </div>
  );
}
