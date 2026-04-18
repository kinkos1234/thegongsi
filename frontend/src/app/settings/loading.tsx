import { Skeleton } from "@/components/Skeleton";

export default function SettingsLoading() {
  return (
    <main className="mx-auto max-w-[720px] px-8 py-16">
      <Skeleton className="h-[12px] w-[80px]" />
      <Skeleton className="mt-4 h-[40px] w-[180px]" />

      {/* BYOK 섹션 */}
      <section className="mt-12 space-y-4">
        <Skeleton className="h-[18px] w-[120px]" />
        <Skeleton className="h-[48px] w-full" />
        <Skeleton className="h-[14px] w-[240px]" />
      </section>

      {/* Alerts 섹션 */}
      <section className="mt-16 space-y-3">
        <Skeleton className="h-[18px] w-[100px]" />
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-[48px] w-full" />
        ))}
      </section>
    </main>
  );
}
