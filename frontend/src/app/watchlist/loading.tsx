import { Skeleton } from "@/components/Skeleton";

export default function WatchlistLoading() {
  return (
    <main className="mx-auto max-w-[1080px] px-8 py-16">
      <Skeleton className="h-[12px] w-[90px]" />
      <Skeleton className="mt-4 h-[40px] w-[200px]" />
      <Skeleton className="mt-3 h-[16px] w-[360px]" />

      <section className="mt-12 space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-[56px] w-full" />
        ))}
      </section>
    </main>
  );
}
