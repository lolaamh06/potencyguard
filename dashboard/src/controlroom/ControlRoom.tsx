// PLACEHOLDER (F2): the Control Room panels are built in F3 to F5. This page only shows which
// data mode is active and what the adapter loaded, so the three modes can be checked.
import type { AdapterSnapshot, Mode } from "../data/types";

const MODE_NAME: Record<Mode, string> = { story: "Story", replay: "Replay", live: "Live" };

export function ControlRoom({ mode, data, backendReachable }: { mode: Mode; data: AdapterSnapshot; backendReachable: boolean | null }) {
  const status = data.status;
  const ids = Object.keys(data.scenarios);
  return (
    <main className="page" id="control-room">
      <h1>Control Room</h1>
      <p>The panels are built in a later phase. This page shows the data source only.</p>
      <p data-testid="data-status">
        Mode: <strong>{MODE_NAME[mode]}</strong>.{" "}
        {status.state === "loading" && "Loading the data."}
        {status.state === "error" && `The data could not be read: ${status.message}`}
        {status.state === "ready" && (mode === "story" ? "Bundled story figures are loaded." : `${status.scenarios} recorded scenarios are loaded.`)}
      </p>
      {status.state === "ready" && status.message && <p data-testid="data-message">{status.message}</p>}
      {mode === "live" && backendReachable !== null && (
        <p data-testid="backend-status">{backendReachable ? "Backend reached (read-only)." : "Backend not reachable."}</p>
      )}
      {ids.length > 0 && <p className="num">{ids.join(", ")}</p>}
      <p>
        Data mode:{" "}
        {(["story", "replay", "live"] as const).map((m) => (
          <a key={m} className="btn" style={{ marginRight: "0.5rem" }} href={`?mode=${m}#/control-room`} aria-current={m === mode ? "true" : undefined}>
            {MODE_NAME[m]}
          </a>
        ))}
      </p>
    </main>
  );
}
