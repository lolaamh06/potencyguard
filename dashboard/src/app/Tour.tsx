// The first-visit guided tour: five steps shown as a card with a highlight on the thing to use.
// It can be skipped at any step and restarted from Help. It also opens the page each step is about.
import { useEffect } from "react";
import { START_HERE } from "../copy/scenarios";
import { goTo, parseRoute } from "./route";
import { TOUR_STEPS, useUi } from "./ui";

const TARGETS = ["tour-start-here", "tour-play", "tour-recommendation", "tour-decide", "tour-proof"];

export function Tour() {
  const step = useUi((s) => s.tourStep);
  const stepTour = useUi((s) => s.stepTour);
  const endTour = useUi((s) => s.endTour);

  useEffect(() => {
    if (step === null) return;
    const info = TOUR_STEPS[step];
    const here = parseRoute(window.location.hash).page;
    if (here !== info.page) goTo(info.page === "shipment" ? { page: "shipment", id: START_HERE } : { page: info.page });
    const mark = () => {
      document.querySelectorAll(".tour-target").forEach((n) => n.classList.remove("tour-target"));
      const el = document.querySelector(`[data-tour="${TARGETS[step]}"]`);
      el?.classList.add("tour-target");
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
    };
    const id = window.setTimeout(mark, 350);
    return () => {
      window.clearTimeout(id);
      document.querySelectorAll(".tour-target").forEach((n) => n.classList.remove("tour-target"));
    };
  }, [step]);

  useEffect(() => {
    if (step === null) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && endTour();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, endTour]);

  if (step === null) return null;
  const info = TOUR_STEPS[step];
  return (
    <aside className="tour" role="dialog" aria-label={`Guided tour, step ${step + 1} of ${TOUR_STEPS.length}`}>
      <p className="tour-count">Step {step + 1} of {TOUR_STEPS.length}</p>
      <h2>{info.title}</h2>
      <p>{info.text}</p>
      <div className="tour-actions">
        <button type="button" className="btn" onClick={() => stepTour(-1)} disabled={step === 0}>Back</button>
        <button type="button" className="btn primary" onClick={() => stepTour(1)}>{step === TOUR_STEPS.length - 1 ? "Finish" : "Next"}</button>
        <button type="button" className="btn quiet" onClick={endTour}>Skip the tour</button>
      </div>
    </aside>
  );
}
