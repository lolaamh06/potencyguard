// About this data: what is real and what is simulated, in plain words, with the technical facts
// (seeds, versions, profile) collapsed. The reference-profile figures are here too.
import story from "../data/bundled/chapter1.json";
import type { AdapterSnapshot, StoryData } from "../data/types";
import { SCENARIO_IDS } from "../controlroom/logic";
import { PageShell } from "./PageShell";

export function AboutPage({ data }: { data: AdapterSnapshot }) {
  const first = SCENARIO_IDS.map((id) => data.scenarios[id]).find(Boolean);
  const ref = (story as unknown as StoryData).profiles.reference;
  const act = (story as unknown as StoryData).profiles.active;
  return (
    <PageShell route={{ page: "about" }} endActions={<><a className="btn" href="#/">Back to Home</a><a className="btn" href="#/story">Watch the story</a></>}>
      <section className="card" aria-labelledby="h-sim">
        <h2 id="h-sim">Sample data from a simulation</h2>
        <p>Everything you see is sample data made by a simulation of an imaginary medicine in an imaginary box. No real shipment, patient, product or company is shown.</p>
        <p>The medicine's strength, the costs and the safe temperature range are illustrative numbers chosen for the demo. They are model outputs, not measurements.</p>
      </section>
      <section className="card" aria-labelledby="h-real">
        <h2 id="h-real">What is real, and what is not</h2>
        <div className="two-col">
          <div>
            <h3>Real</h3>
            <ul className="why">
              <li>The calculations: strength, safe life used, the safety checks and the recommendation are done by the project's own code.</li>
              <li>The signed records and the checks on them are real. The results on the Proof page come from real checks on copies of the records.</li>
              <li>Each shipment's numbers come from a recorded run, and the same run always gives the same numbers.</li>
            </ul>
          </div>
          <div>
            <h3>Simulated or a stand-in</h3>
            <ul className="why">
              <li>The temperature readings are made by a simulator, not read from a real sensor.</li>
              <li>The enterprise system is a demo stand-in. Pressing Approve changes this screen only, and nothing is sent anywhere.</li>
              <li>The route and places on the globe are illustrative.</li>
            </ul>
          </div>
        </div>
      </section>
      <section className="card" aria-labelledby="h-ref">
        <h2 id="h-ref">Two sets of constants, both illustrative</h2>
        <p>The demo uses one set of medicine constants. A second set, taken from the team's own document, gives different figures for the same two sample journeys (8 hours at 12 °C, and 24 hours at 30 °C). Both are model outputs for an imaginary product.</p>
        <table className="table">
          <thead><tr><th>Constants</th><th className="r">Journey A: safe life used</th><th className="r">Journey B: safe life used</th></tr></thead>
          <tbody>
            <tr><td>{act.label} (used in the demo)</td><td className="num r">{act.journeys.A.shelf_life_used_percent.toFixed(2)}%</td><td className="num r">{act.journeys.B.shelf_life_used_percent.toFixed(2)}%</td></tr>
            <tr><td>{ref.label}</td><td className="num r">{ref.journeys.A.shelf_life_used_percent.toFixed(2)}%</td><td className="num r">{ref.journeys.B.shelf_life_used_percent.toFixed(2)}%</td></tr>
          </tbody>
        </table>
      </section>
      <details className="details">
        <summary>Technical details</summary>
        <div className="details-body">
          {first ? (
            <dl className="facts wide">
              <div><dt>Source of the readings</dt><dd>{first.provenance.source} (simulated sensor feed)</dd></div>
              <div><dt>Enterprise adapter</dt><dd>{first.provenance.sap_adapter_mode} (a demo stand-in)</dd></div>
              <div><dt>Software</dt><dd>{first.provenance.software_version}; dashboard Phase F5</dd></div>
              <div><dt>Planner seed</dt><dd className="num">{first.provenance.planner_seed}</dd></div>
              {SCENARIO_IDS.map((id) => data.scenarios[id] && <div key={id}><dt>Recording seed: {id}</dt><dd className="num">{String(data.scenarios[id].provenance.recording_seed)}</dd></div>)}
              <div><dt>Signing key id (a test key)</dt><dd className="num">{first.provenance.signing_key_id}</dd></div>
              <div><dt>Constants in use</dt><dd>Ea/R {first.meta.product.Ea_over_R}, reference {first.meta.product.T_ref_c} °C, shelf life {first.meta.product.tau_max_h} h at the reference temperature</dd></div>
              <div><dt>Data kind</dt><dd>a replay of recordings; the Story uses the same files</dd></div>
            </dl>
          ) : (
            <p className="muted">{data.status.state === "loading" ? "Loading…" : "The technical facts are not available."}</p>
          )}
          <p className="note">Signing protects records after signing. It does not stop a false sensor value.</p>
        </div>
      </details>
    </PageShell>
  );
}
