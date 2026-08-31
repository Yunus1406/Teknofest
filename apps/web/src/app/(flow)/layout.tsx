import { StageRail } from "@/components/layout/StageRail";

export default function FlowLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <StageRail />
      <main className="flex-1 px-8 py-8 md:px-12">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
