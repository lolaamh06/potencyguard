// The chain of records as a row of tokens: verified, broken, dimmed after a break, or removed.
import type { Token } from "../controlroom/logic";

export function Ribbon({ tokens, label }: { tokens: Token[]; label: string }) {
  return (
    <div className="ribbon" role="img" aria-label={label}>
      {tokens.map((t) => (
        <span key={t.index} className={`tok ${t.status}`} title={`record ${t.index}`}>
          {t.status === "verified" ? "✓" : t.status === "broken" ? "!" : t.status === "removed" ? "–" : "·"}
        </span>
      ))}
    </div>
  );
}
