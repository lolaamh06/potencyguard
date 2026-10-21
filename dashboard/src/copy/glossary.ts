// The one place for every user-facing term, in two registers: Simple (plain words, for a first-time
// visitor) and Technical (the engineers' words). Each has a one-sentence explanation. Components ask
// for a term by id and the reading mode; they never type these words by hand. Plain wording must stay
// TRUE: a Simple label may be shorter, never softer.
export type ReadingMode = "simple" | "technical";

interface Register {
  label: string;
  explain: string;
}

export interface Entry {
  simple: Register;
  technical: Register;
  /** Not shown at all in Simple mode (appears only under Technical). */
  hiddenInSimple?: boolean;
}

export const GLOSSARY = {
  potency: {
    simple: { label: "Medicine strength left", explain: "How strong the medicine still is, as a share of its full strength." },
    technical: { label: "Potency", explain: "The modelled potency of the product from its temperature history, as a percentage of its starting value." },
  },
  shelfLifeUsed: {
    simple: { label: "Share of its safe life already spent", explain: "How much of the medicine's safe life the journey has used up so far." },
    technical: { label: "Shelf life used", explain: "Equivalent time at the reference temperature divided by the product's shelf life, as a percentage." },
  },
  remainingLife: {
    simple: { label: "Safe life remaining", explain: "How much safe life is left, counted as time at the ideal temperature." },
    technical: { label: "Remaining life", explain: "The product's shelf life minus the equivalent time already used, in hours at the reference temperature." },
  },
  mkt: {
    simple: { label: "Average effective temperature", explain: "A single temperature that has the same effect on the medicine as the whole journey had." },
    technical: { label: "Mean kinetic temperature (MKT)", explain: "The constant temperature that would cause the same degradation as the recorded temperature history." },
  },
  expectedTemp: {
    simple: { label: "Expected temperature", explain: "What the box temperature should be, according to a physics model of the box and the outside weather." },
    technical: { label: "Expected temperature (thermal twin)", explain: "The one-step-ahead prediction of the thermal twin, a model of the box fed with the ambient temperature." },
    hiddenInSimple: false,
  },
  difference: {
    simple: { label: "Difference from expected", explain: "How far the measured temperature is from the expected temperature." },
    technical: { label: "Difference from expected (residual)", explain: "Measured temperature minus the twin's prediction, in degrees Celsius." },
    hiddenInSimple: true,
  },
  alarmStrip: {
    simple: { label: "Alarm strip", explain: "A running total of how long the readings have drifted away from what was expected." },
    technical: { label: "Alarm strip (CUSUM)", explain: "The cumulative sum of the residual; an alarm fires when it passes the threshold h." },
    hiddenInSimple: true,
  },
  trust: {
    simple: { label: "Can we trust this data?", explain: "Whether the checks found the temperature readings believable." },
    technical: { label: "Trust level", explain: "The result of the physics and sanity checks on the readings: trusted, low confidence or untrusted." },
  },
  trust_trusted: {
    simple: { label: "Yes", explain: "The readings passed the checks." },
    technical: { label: "Trusted", explain: "No check fired and the twin is in date." },
  },
  trust_low_confidence: {
    simple: { label: "Partly", explain: "Some checks raised a doubt, so the readings are only partly believable." },
    technical: { label: "Low confidence", explain: "A check raised a doubt that is not yet proof." },
  },
  trust_untrusted: {
    simple: { label: "No", explain: "The checks found the readings impossible or inconsistent, so we cannot rely on them." },
    technical: { label: "Untrusted", explain: "Proof-grade checks fired (for example an impossible step in temperature)." },
  },
  verdict_ok: {
    simple: { label: "Everything looks normal", explain: "The readings behave the way a real box would." },
    technical: { label: "ok", explain: "No detector has fired." },
  },
  verdict_thermal_anomaly: {
    simple: { label: "The box is warming or cooling unexpectedly", explain: "The temperature is moving away from what the physics model expects, which looks like a real heat problem." },
    technical: { label: "thermal anomaly", explain: "The residual has drifted past the alarm threshold in a way consistent with a real excursion." },
  },
  verdict_sensor_glitch: {
    simple: { label: "A reading looks like a glitch", explain: "One or two readings look like sensor noise, not a real change." },
    technical: { label: "sensor glitch", explain: "A short, isolated disagreement that looks like a sensor fault." },
  },
  verdict_suspected_falsification: {
    simple: { label: "The readings look false", explain: "The readings break the rules of physics, so someone or something may have changed them." },
    technical: { label: "suspected falsification", explain: "Proof-grade checks fired: the readings are physically impossible for this box." },
  },
  worstCaseBound: {
    simple: { label: "Worst-case bound, not an estimate", explain: "A cautious limit we use when the data cannot be trusted; it is not our best guess." },
    technical: { label: "Worst-case bound, not an estimate", explain: "The planner's start state from the worst credible history when the trust level is not trusted." },
  },
  expectedLoss: {
    simple: { label: "Average cost", explain: "The cost you would expect on average if this action were taken many times." },
    technical: { label: "Expected loss", explain: "The probability-weighted mean of the loss over the simulated outcomes." },
  },
  worstFive: {
    simple: { label: "Cost in the worst 5% of cases", explain: "The average cost in the unluckiest 5 out of every 100 outcomes." },
    technical: { label: "Worst-5% cost (CVaR)", explain: "The conditional value at risk: the mean loss in the worst 5% of simulated outcomes." },
  },
  closeCall: {
    simple: { label: "Close call", explain: "Two options were almost tied, so a person should choose." },
    technical: { label: "Close call", explain: "The leading actions are within the backend's near-tie margin." },
  },
  action_continue: {
    simple: { label: "Carry on", explain: "Keep the shipment on its current plan." },
    technical: { label: "Continue", explain: "Keep going on the current plan." },
  },
  action_expedite: {
    simple: { label: "Speed up delivery", explain: "Move the shipment faster to shorten its time at risk." },
    technical: { label: "Expedite", explain: "Speed the shipment up." },
  },
  action_reroute: {
    simple: { label: "Send to the nearest depot", explain: "Divert the shipment to a depot where it can be checked or cooled." },
    technical: { label: "Reroute to depot", explain: "Divert the shipment to the nearest depot." },
  },
  action_resource: {
    simple: { label: "Replace the shipment", explain: "Send a new shipment from another source." },
    technical: { label: "Re-source", explain: "Replace the shipment from another source." },
  },
  action_hold: {
    simple: { label: "Hold for review", explain: "Stop the shipment and have a person look at it before anything else happens." },
    technical: { label: "Quarantine", explain: "Hold the shipment pending review." },
  },
  signedRecord: {
    simple: { label: "Signed record", explain: "A reading stored together with a digital stamp that shows if it was changed afterwards." },
    technical: { label: "Signed record", explain: "A canonical record with an Ed25519 signature, chained to the previous record by its hash." },
  },
  chain: {
    simple: { label: "Chain of records", explain: "Records linked one to the next, so changing one breaks every link after it." },
    technical: { label: "Hash chain", explain: "Each record's hash covers the previous hash, the record bytes and the signature." },
  },
  anchor: {
    simple: { label: "End-marker", explain: "A signed note of how many records there should be, which lets us notice deleted records at the end." },
    technical: { label: "Anchor", explain: "A signed statement of the latest entry, needed to detect tail truncation." },
  },
} satisfies Record<string, Entry>;

export type TermId = keyof typeof GLOSSARY;
export const TERM_IDS = Object.keys(GLOSSARY) as TermId[];

/** The label for a term in the chosen reading mode. */
export function term(id: TermId, mode: ReadingMode): string {
  return GLOSSARY[id][mode].label;
}

/** The one-sentence explanation of a term in the chosen reading mode. */
export function explain(id: TermId, mode: ReadingMode): string {
  return GLOSSARY[id][mode].explain;
}

/** True when the term should not be shown at all in this mode. */
export function hiddenIn(id: TermId, mode: ReadingMode): boolean {
  const e: Entry = GLOSSARY[id];
  return mode === "simple" && e.hiddenInSimple === true;
}

const ACTION_IDS: Record<string, TermId> = {
  continue: "action_continue",
  expedite: "action_expedite",
  reroute_to_depot: "action_reroute",
  re_source: "action_resource",
  quarantine: "action_hold",
};

/** Glossary id for an exported action name (null for a name we do not know). */
export function actionTerm(name: string): TermId | null {
  return ACTION_IDS[name] ?? null;
}

export function actionLabel(name: string, mode: ReadingMode): string {
  const id = actionTerm(name);
  return id ? term(id, mode) : name.replace(/_/g, " ");
}

const ACTION_SENTENCES: Record<string, string> = {
  continue: "carry on as planned",
  expedite: "speed up the delivery",
  reroute_to_depot: "send it to the nearest depot",
  re_source: "replace the shipment",
  quarantine: "hold it for review",
};

/** The action as a verb phrase for a sentence ("send it to the nearest depot"). */
export function actionPhrase(name: string): string {
  return ACTION_SENTENCES[name] ?? name.replace(/_/g, " ");
}

export function verdictTerm(verdict: string): TermId | null {
  const id = `verdict_${verdict}` as TermId;
  return id in GLOSSARY ? id : null;
}

export function verdictLabel(verdict: string, mode: ReadingMode): string {
  const id = verdictTerm(verdict);
  return id ? term(id, mode) : verdict.replace(/_/g, " ");
}

export function trustTerm(level: string): TermId | null {
  const id = `trust_${level}` as TermId;
  return id in GLOSSARY ? id : null;
}

export function trustAnswer(level: string, mode: ReadingMode): string {
  const id = trustTerm(level);
  return id ? term(id, mode) : level.replace(/_/g, " ");
}

/** Every term the product shows; a test asserts each is present and complete. */
export const REQUIRED_TERMS: TermId[] = [
  "potency", "shelfLifeUsed", "remainingLife", "mkt", "expectedTemp", "difference", "alarmStrip", "trust",
  "trust_trusted", "trust_low_confidence", "trust_untrusted", "verdict_ok", "verdict_thermal_anomaly",
  "verdict_sensor_glitch", "verdict_suspected_falsification", "worstCaseBound", "expectedLoss", "worstFive",
  "closeCall", "action_continue", "action_expedite", "action_reroute", "action_resource", "action_hold",
  "signedRecord", "chain", "anchor",
];
