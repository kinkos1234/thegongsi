export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bg-bg-2 animate-pulse ${className}`} />;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="py-16 text-center">
      <p className="font-serif text-[20px] text-fg-2">{title}</p>
      {hint && <p className="mt-3 text-[13px] text-fg-3">{hint}</p>}
    </div>
  );
}
