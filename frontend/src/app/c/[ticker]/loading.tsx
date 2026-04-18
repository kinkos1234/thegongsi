import { Skeleton } from "@/components/Skeleton";

// /c/[ticker] SSR 은 Fly API 4개 (company/disclosures/quote/memo) 병렬 호출로
// 콜드 스타트 시 2-5초 걸림. 그 동안 이전 화면이 유지되는 대신 구조를 유지한
// 스켈레톤을 먼저 보여준다.
export default function CompanyLoading() {
  return (
    <main className="mx-auto max-w-[1080px] px-8 py-16">
      {/* CompanyHeader */}
      <header className="flex items-baseline justify-between">
        <div className="space-y-3">
          <Skeleton className="h-[44px] w-[280px]" />
          <Skeleton className="h-[18px] w-[160px]" />
        </div>
        <div className="text-right space-y-3">
          <Skeleton className="h-[28px] w-[120px] ml-auto" />
          <Skeleton className="h-[16px] w-[80px] ml-auto" />
        </div>
      </header>

      {/* TodayAnomalies / Chart */}
      <section className="mt-12">
        <Skeleton className="h-[12px] w-[120px]" />
        <Skeleton className="mt-4 h-[120px] w-full" />
      </section>

      {/* DD 메모 */}
      <section className="mt-12 border border-border/50 p-8 space-y-4">
        <Skeleton className="h-[28px] w-[120px]" />
        <Skeleton className="h-[16px] w-full" />
        <Skeleton className="h-[16px] w-[85%]" />
        <Skeleton className="h-[16px] w-[70%]" />
      </section>

      {/* 공시 */}
      <section className="mt-16 space-y-3">
        <Skeleton className="h-[24px] w-[60px]" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[36px] w-full" />
        ))}
      </section>
    </main>
  );
}
