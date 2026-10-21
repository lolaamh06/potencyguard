// Chapter 1: "Two alarms. One verdict." Two journeys cross the same alarm line and get the same
// REJECT stamp; the vials tell them apart. The time handle uses the tested TypeScript potency
// mirror; the end-of-journey figures printed under it are the exported ones.
import { useCallback, useEffect, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { constantsFor, scrubJourney } from "../data/story";
import type { StoryData } from "../data/types";
import { MODEL_LABEL, Scene, Missing, span, useChapterTick } from "./common";

const W = 560;
const H = 220;
const MAX_H = 24;
const MAX_T = 36;
const x = (h: number) => 40 + (h / MAX_H) * (W - 60);
const y = (c: number) => H - 28 - (c / MAX_T) * (H - 50);

function Trace({ id, temp, hours, label, story }: { id: string; temp: number; hours: number; label: string; story: StoryData }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label}: ${hours} hours at ${temp} degrees Celsius, above the ${story.threshold_c} degree alarm line`}>
      <line x1={40} x2={W - 20} y1={y(story.threshold_c)} y2={y(story.threshold_c)} stroke="var(--ember-400)" strokeDasharray="5 5" />
      <text x={W - 22} y={y(story.threshold_c) + 15} textAnchor="end" fill="var(--ember-400)" fontSize="12">alarm line {story.threshold_c} °C</text>
      <line x1={40} x2={40} y1={12} y2={H - 28} stroke="var(--line-strong)" />
      <line x1={40} x2={W - 20} y1={H - 28} y2={H - 28} stroke="var(--line-strong)" />
      {[0, 8, 16, 24].map((h) => (
        <text key={h} x={x(h)} y={H - 10} textAnchor="middle" fill="var(--mist-hi)" fontSize="12">{h} h</text>
      ))}
      <text x={6} y={22} fill="var(--mist-hi)" fontSize="12">°C</text>
      <text x={x(0) + 6} y={y(temp) + 17} fill="var(--frost)" fontSize="13" fontWeight="600">{label}</text>
      <path id={`trace-${id}`} d={`M ${x(0)} ${y(temp)} L ${x(hours)} ${y(temp)}`} stroke="var(--ice-400)" strokeWidth="3.5" fill="none" pathLength={1} strokeDasharray="1" strokeDashoffset="1" strokeLinecap="round" />
      <g id={`stamp-${id}`} opacity="0" transform={`translate(${x(hours) - 104} ${y(temp) - 46})`}>
        <rect width="104" height="34" rx="4" fill="none" stroke="var(--danger-text)" strokeWidth="2.5" />
        <text x="52" y="24" textAnchor="middle" fill="var(--danger-text)" fontSize="20" fontWeight="700" letterSpacing="2">REJECT</text>
      </g>
    </svg>
  );
}

function Vial({ id }: { id: string }) {
  return (
    <svg className="vial" viewBox="0 0 90 150" width="90" role="img" aria-label="A vial; its glow shows shelf life remaining">
      <defs>
        <radialGradient id={`glow-${id}`} cx="50%" cy="60%" r="60%">
          <stop offset="0%" stopColor="var(--ice-300)" />
          <stop offset="100%" stopColor="var(--ice-400)" />
        </radialGradient>
      </defs>
      <rect id={`halo-${id}`} x="5" y="30" width="80" height="100" rx="40" fill="var(--ice-400)" opacity="0.2" style={{ filter: "blur(14px)" }} />
      <rect x="24" y="22" width="42" height="110" rx="10" fill="none" stroke="var(--mist-hi)" strokeWidth="2" />
      <rect x="30" y="8" width="30" height="16" rx="3" fill="var(--mist)" />
      <rect id={`liquid-${id}`} x="28" y="60" width="34" height="68" rx="7" fill={`url(#glow-${id})`} />
    </svg>
  );
}

export function Chapter1({ story }: { story: StoryData | null }) {
  const root = useRef<HTMLDivElement>(null);
  const handle = useRef<HTMLInputElement>(null);
  const touched = useRef(false);
  const fraction = useRef(0);
  const reduced = useAppStore((s) => s.reducedMotion);

  const paint = useCallback(
    (f: number) => {
      const el = root.current;
      if (!el || !story) return;
      const c = constantsFor(story, "active");
      for (const key of ["A", "B"] as const) {
        const j = story.journeys[key];
        const r = scrubJourney(j.temp_c, j.hours, f, c);
        const path = el.querySelector<SVGPathElement>(`#trace-${key}`);
        // the trace draws to the scrubbed hour on the shared 24-hour axis
        if (path) path.style.strokeDashoffset = String(1 - Math.min(1, f));
        const used = 1 - Math.min(1, r.shelfLifeUsedPercent / 100);
        const liquid = el.querySelector<SVGRectElement>(`#liquid-${key}`);
        if (liquid) liquid.style.opacity = String(0.18 + 0.82 * used);
        const halo = el.querySelector<SVGRectElement>(`#halo-${key}`);
        if (halo) halo.style.opacity = String(0.05 + 0.3 * used);
        const text = el.querySelector<HTMLElement>(`#read-${key}`);
        if (text) text.textContent = `${r.hours.toFixed(1)} h: potency ${(r.potency * 100).toFixed(2)}%, shelf life used ${r.shelfLifeUsedPercent.toFixed(2)}%`;
      }
    },
    [story],
  );

  useChapterTick(1, (t) => {
    const el = root.current;
    if (!el) return;
    if (!touched.current) {
      fraction.current = reduced ? 1 : span(t, 0.12, 0.62);
      if (handle.current) handle.current.value = String(fraction.current);
    }
    paint(fraction.current);
    const stamps = reduced ? 1 : span(t, 0.62, 0.72);
    el.querySelectorAll<SVGGElement>("[id^=stamp-]").forEach((s) => (s.style.opacity = String(stamps)));
    const line = (id: string, from: number) => {
      const node = document.getElementById(id);
      if (node) node.style.opacity = String(reduced ? 1 : span(t, from, from + 0.1));
    };
    line("c1-l1", 0.02);
    line("c1-l2", 0.14);
    line("c1-l3", 0.7);
    line("c1-l4", 0.86);
  });

  useEffect(() => {
    fraction.current = reduced ? 1 : fraction.current;
  }, [reduced]);

  return (
    <Scene index={1}>
      <div className="copy">
        <h2>Two alarms. One verdict.</h2>
        <p id="c1-l1">Two journeys. The alarm gives them the same verdict.</p>
        <p id="c1-l2">8 hours at 12 °C spends almost nothing. A day at 30 °C spends far more.</p>
        <p id="c1-l3">The alarm cannot tell the difference. The medicine can.</p>
        <p id="c1-l4" className="quiet">At the other end, a clinic is still waiting.</p>
      </div>
      <div className="figure" ref={root}>
        {!story ? (
          <Missing what="The Chapter 1 figures" />
        ) : (
          <>
            <div className="pair">
              <div>
                <Trace id="A" temp={story.journeys.A.temp_c} hours={story.journeys.A.hours} label="Journey A" story={story} />
                <Vial id="A" />
                <p id="read-A" className="num read" />
              </div>
              <div>
                <Trace id="B" temp={story.journeys.B.temp_c} hours={story.journeys.B.hours} label="Journey B" story={story} />
                <Vial id="B" />
                <p id="read-B" className="num read" />
              </div>
            </div>
            <label className="handle">
              <span>Move through both journeys</span>
              <input
                ref={handle}
                type="range"
                min={0}
                max={1}
                step={0.005}
                defaultValue={0}
                onInput={(e) => {
                  touched.current = true;
                  fraction.current = Number((e.target as HTMLInputElement).value);
                  paint(fraction.current);
                }}
              />
            </label>
            <p className="label-model">
              {MODEL_LABEL}. At the end of each journey, shelf life used: A {story.profiles.active.journeys.A.shelf_life_used_percent.toFixed(2)}%, B {story.profiles.active.journeys.B.shelf_life_used_percent.toFixed(1)}%. The glow shows shelf life remaining.
            </p>
            <details className="prov">
              <summary>Provenance</summary>
              <p>
                {story.profiles.active.label} is shown above. {story.profiles.reference.label}: A {story.profiles.reference.journeys.A.shelf_life_used_percent.toFixed(2)}%, B {story.profiles.reference.journeys.B.shelf_life_used_percent.toFixed(2)}%. Both are model outputs for an imaginary product, from our own potency code.
              </p>
            </details>
          </>
        )}
      </div>
    </Scene>
  );
}
