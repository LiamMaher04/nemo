/**
 * The quiet index line that opens each section: a hairline, the section name,
 * and its number. Replaces generic "eyebrow" labels.
 */
export function SectionLabel({ index, children }: { index: string; children: React.ReactNode }) {
  return (
    <div className="rule flex items-baseline justify-between gap-6 pt-5 text-base">
      <span className="font-medium">{children}</span>
      <span className="font-heading tabular-nums opacity-80" aria-hidden="true">
        {index}
      </span>
    </div>
  );
}
