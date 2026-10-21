import { describe, expect, it } from "vitest";
import baseline from "../../public/replay/baseline_ok.json";
import door from "../../public/replay/door_open_excursion.json";
import hidden from "../../public/replay/hidden_spoilage.json";
import reefer from "../../public/replay/reefer_failure.json";
import spoof from "../../public/replay/spoof_attempt.json";
import { SCENARIO_IDS } from "../controlroom/logic";
import type { ReplayFile } from "../data/types";
import { GLOSSARY, REQUIRED_TERMS, TERM_IDS, actionLabel, actionPhrase, actionTerm, explain, hiddenIn, term, trustAnswer, verdictLabel } from "./glossary";
import { STATUS_WORDS, headline, plainReasons, statusKind, strengthPercent, whatHappened } from "./headline";
import { SCENARIO_COPY, START_HERE } from "./scenarios";

const replays: Record<string, ReplayFile> = {
  baseline_ok: baseline as unknown as ReplayFile,
  door_open_excursion: door as unknown as ReplayFile,
  reefer_failure: reefer as unknown as ReplayFile,
  spoof_attempt: spoof as unknown as ReplayFile,
  hidden_spoilage: hidden as unknown as ReplayFile,
};

describe("glossary", () => {
  it("has every required term, in both registers, with a label and a one-sentence explanation", () => {
    for (const id of REQUIRED_TERMS) expect(TERM_IDS, id).toContain(id);
    for (const id of TERM_IDS) {
      for (const mode of ["simple", "technical"] as const) {
        const label = term(id, mode);
        const text = explain(id, mode);
        expect(label.trim().length, `${id} ${mode} label`).toBeGreaterThan(0);
        expect(text.trim().length, `${id} ${mode} explanation`).toBeGreaterThan(10);
        expect(text.trim().endsWith("."), `${id} ${mode} ends with a full stop`).toBe(true);
        expect((text.match(/\./g) ?? []).length, `${id} ${mode} is one sentence`).toBe(1);
      }
    }
  });

  it("uses the agreed plain wording in Simple mode", () => {
    expect(term("potency", "simple")).toBe("Medicine strength left");
    expect(term("shelfLifeUsed", "simple")).toBe("Share of its safe life already spent");
    expect(term("trust", "simple")).toBe("Can we trust this data?");
    expect(term("worstFive", "simple")).toBe("Cost in the worst 5% of cases");
    expect(term("action_hold", "simple")).toBe("Hold for review");
    expect(term("action_reroute", "simple")).toBe("Send to the nearest depot");
    expect(term("action_continue", "simple")).toBe("Carry on");
    expect(term("action_expedite", "simple")).toBe("Speed up delivery");
    expect(term("action_resource", "simple")).toBe("Replace the shipment");
  });

  it("answers the trust question with Yes, Partly or No", () => {
    expect(trustAnswer("trusted", "simple")).toBe("Yes");
    expect(trustAnswer("low_confidence", "simple")).toBe("Partly");
    expect(trustAnswer("untrusted", "simple")).toBe("No");
    expect(trustAnswer("untrusted", "technical")).toBe("Untrusted");
  });

  it("keeps the technical words in Technical mode and hides CUSUM and residual in Simple mode", () => {
    expect(term("worstFive", "technical")).toContain("CVaR");
    expect(term("alarmStrip", "technical")).toContain("CUSUM");
    expect(term("difference", "technical")).toContain("residual");
    expect(term("expectedTemp", "technical")).toContain("twin");
    expect(hiddenIn("alarmStrip", "simple")).toBe(true);
    expect(hiddenIn("difference", "simple")).toBe(true);
    expect(hiddenIn("alarmStrip", "technical")).toBe(false);
    expect(hiddenIn("potency", "simple")).toBe(false);
    for (const mode of ["simple"] as const) {
      expect(term("alarmStrip", mode)).not.toMatch(/cusum/i);
      expect(term("difference", mode)).not.toMatch(/residual/i);
    }
  });

  it("switches the register for the same term", () => {
    for (const id of TERM_IDS) {
      const simple = term(id, "simple");
      const technical = term(id, "technical");
      expect(typeof simple).toBe("string");
      expect(typeof technical).toBe("string");
    }
    expect(term("potency", "simple")).not.toBe(term("potency", "technical"));
  });

  it("maps every exported action, verdict and falls back calmly for an unknown one", () => {
    for (const r of Object.values(replays)) {
      for (const a of r.decision.actions) expect(actionTerm(a.name), a.name).not.toBeNull();
    }
    expect(actionLabel("reroute_to_depot", "simple")).toBe("Send to the nearest depot");
    expect(actionLabel("something_new", "simple")).toBe("something new");
    expect(verdictLabel("suspected_falsification", "simple")).toContain("false");
    expect(verdictLabel("mystery", "simple")).toBe("mystery");
    expect(actionPhrase("quarantine")).toBe("hold it for review");
    expect(Object.keys(GLOSSARY).length).toBeGreaterThanOrEqual(REQUIRED_TERMS.length);
  });
});

describe("plain headline sentences for the five sample shipments (true statements from the data)", () => {
  it("has plain copy for exactly the five scenarios, and a start-here card", () => {
    expect(Object.keys(SCENARIO_COPY).sort()).toEqual([...SCENARIO_IDS].sort());
    expect(SCENARIO_IDS).toContain(START_HERE);
  });

  it.each(SCENARIO_IDS)("%s: says what happened, what we recommend and who approves", (id) => {
    const r = replays[id];
    const h = headline(r);
    expect(h).toContain(`We recommend: ${actionPhrase(r.decision.chosen_action)}.`);
    expect(h).toContain(r.decision.needs_human ? "A person needs to approve this." : "approved automatically");
    expect(h.length).toBeLessThan(420);
  });

  it("untrusted shipments say the data cannot be trusted and that a person must approve", () => {
    for (const id of ["spoof_attempt", "hidden_spoilage"] as const) {
      const r = replays[id];
      expect(r.decision.trust_level).toBe("untrusted");
      const h = headline(r);
      expect(h).toMatch(/cannot trust this data/);
      expect(h).toContain("A person needs to approve this.");
      expect(statusKind(r)).toBe("not_trusted");
      expect(plainReasons(r).join(" ")).toMatch(/do not trust/);
    }
  });

  it("a normal journey says the temperature stayed in range and that nobody has to approve it", () => {
    const r = replays.baseline_ok;
    expect(whatHappened(r)).toBe("The temperature stayed in its safe range the whole way.");
    expect(statusKind(r)).toBe("good");
    expect(headline(r)).toContain("approved automatically");
  });

  it("an excursion reads its hours from the data", () => {
    for (const id of ["door_open_excursion", "reefer_failure"] as const) {
      const r = replays[id];
      expect(whatHappened(r)).toMatch(/^The temperature left its safe range at about \d+(\.\d)? hours/);
      expect(statusKind(r)).toBe("problem");
    }
  });

  it("status words are the agreed four and the strength figure comes from the frames", () => {
    expect(Object.values(STATUS_WORDS).sort()).toEqual(["All good", "Data not trusted", "Needs a person", "Problem found"]);
    const r = replays.baseline_ok;
    const last = r.frames.filter((f) => f.t_s <= r.meta.checkpoint_h * 3600).pop()!;
    expect(strengthPercent(r)).toBeCloseTo(last.potency * 100, 9);
  });

  it("never uses a hard-to-read technical word in the Simple headline", () => {
    for (const r of Object.values(replays)) {
      expect(headline(r)).not.toMatch(/CUSUM|CVaR|residual|twin|quarantine|trust level/i);
    }
  });
});
