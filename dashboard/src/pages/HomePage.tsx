// Home: two plain sentences, a three-step picture of how it works, and two big buttons. The globe
// is the calm background (the canvas behind the page).
import { useUi } from "../app/ui";

const STEPS = [
  { n: "1", title: "Measure", text: "Sensors inside the box send the temperature, again and again." },
  { n: "2", title: "Check", text: "The system checks the readings and works out how strong the medicine still is." },
  { n: "3", title: "Decide", text: "It recommends what to do. A person makes the final call." },
];

export function HomePage() {
  const tourSeen = useUi((s) => s.tourSeen);
  const startTour = useUi((s) => s.startTour);
  const endTour = useUi((s) => s.endTour);
  return (
    <main id="content" className="page home" tabIndex={-1}>
      <section className="hero">
        <h1>Know if your medicine is still safe.</h1>
        <p className="hero-text">
          Some medicines spoil if they get too warm on the way to a clinic. PotencyGuard watches the temperature, works out how strong the medicine still is, and recommends what to do, with a person making the final decision.
        </p>
        <div className="btn-row big-row">
          <a className="btn primary big" href="#/story">Watch the story</a>
          <a className="btn big" href="#/shipments">Try the demo</a>
        </div>
        {!tourSeen && (
          <p className="tour-offer" role="note">
            First time here? <button type="button" className="link-btn" onClick={startTour}>Take a one-minute tour</button> or <button type="button" className="link-btn" onClick={endTour}>skip it</button>.
          </p>
        )}
      </section>
      <section aria-labelledby="how" className="how">
        <h2 id="how">How it works</h2>
        <ol className="steps">
          {STEPS.map((s, i) => (
            <li key={s.n} className="step">
              <svg viewBox="0 0 64 64" width="56" height="56" aria-hidden="true">
                <circle cx="32" cy="32" r="29" fill="none" stroke="var(--ice-400)" strokeWidth="3" />
                {i === 0 && <g fill="none" stroke="var(--ice-400)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"><path d="M28 14a4 4 0 0 1 8 0v22a9 9 0 1 1-8 0z" /><path d="M32 24v16" /></g>}
                {i === 1 && <path d="M18 34l9 9 19-21" fill="none" stroke="var(--verify)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />}
                {i === 2 && <g fill="none" stroke="var(--planner-300)" strokeWidth="4" strokeLinecap="round"><circle cx="32" cy="24" r="7" /><path d="M17 49c2-9 8-13 15-13s13 4 15 13" /></g>}
              </svg>
              <h3><span className="step-n">{s.n}</span> {s.title}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
