// The TypeScript potency mirror against BOTH shared vector files (shared/test-vectors/).
// The vector files state no tolerance, and the Python tests use a relative 1e-14 for the closed
// forms. Both sides use IEEE doubles, but Math.exp and Math.log may differ from the C library's
// in the last bit, so the comparison here is a relative 1e-12. Nothing else is loosened.
import { describe, expect, it } from "vitest";
import active from "../../../shared/test-vectors/potency_vectors.json";
import reference from "../../../shared/test-vectors/potency_vectors_team_document.json";
import {
  PotencyTracker,
  accelerationFactor,
  equivalentReferenceTimeH,
  hoursToMinPotencyAtTemp,
  potencyFromTauEq,
  shelfLifeUsedFraction,
  timeWeightedMktC,
  type ProductConstants,
} from "./mirror";

const REL = 1e-12;

function close(actual: number | null, expected: number | null, label: string): void {
  if (expected === null) {
    expect(actual, label).toBeNull();
    return;
  }
  expect(actual, label).not.toBeNull();
  const a = actual as number;
  const scale = Math.max(Math.abs(expected), 1e-300);
  const err = Math.abs(a - expected) / scale;
  expect(err <= REL || Math.abs(a - expected) <= 1e-15, `${label}: ${a} vs ${expected} (rel ${err})`).toBe(true);
}

const files = [
  { name: "active profile", file: active },
  { name: "reference profile", file: reference },
] as const;

describe.each(files)("potency mirror against $name vectors", ({ file }) => {
  const c = file.meta.constants as ProductConstants;

  it("acceleration factor", () => {
    for (const row of file.af_cases) {
      close(accelerationFactor(row.temp_c, c), row.expected_af, `AF(${row.temp_c})`);
    }
    expect(file.af_cases.length).toBeGreaterThanOrEqual(10);
  });

  it("equivalent time, potency, shelf life used and mean kinetic temperature", () => {
    for (const row of file.tau_cases) {
      const tau = equivalentReferenceTimeH(row.temps_c, row.dts_h, c);
      close(tau, row.expected_tau_eq_h, `${row.name} tau_eq`);
      close(potencyFromTauEq(tau, c), row.expected_potency, `${row.name} potency`);
      close(shelfLifeUsedFraction(tau, c), row.expected_shelf_life_used_fraction, `${row.name} used`);
      close(timeWeightedMktC(row.temps_c, row.dts_h, c), row.expected_mkt_c, `${row.name} MKT`);
    }
  });

  it("streaming tracker: statuses, running totals and final state of every case", () => {
    expect(file.tracker_cases.length).toBe(7);
    for (const row of file.tracker_cases) {
      const tracker = new PotencyTracker(c);
      row.readings.forEach((reading, i) => {
        const state = tracker.update(reading.t_s, reading.temp_c);
        expect(state.status, `${row.name} status ${i}`).toBe(row.expected_statuses[i]);
        const expected = row.expected_per_sample[i];
        expect(state.status, `${row.name} per-sample status ${i}`).toBe(expected.status);
        close(state.tau_eq_h, expected.tau_eq_h, `${row.name} tau_eq ${i}`);
        expect(state.samples_excluded, `${row.name} excluded ${i}`).toBe(expected.samples_excluded);
      });
      const final = tracker.snapshot();
      const want = row.expected_final_state;
      close(final.t_s, want.t_s, `${row.name} t_s`);
      close(final.tau_eq_h, want.tau_eq_h, `${row.name} final tau_eq`);
      close(final.potency, want.potency, `${row.name} final potency`);
      close(final.shelf_life_used_fraction, want.shelf_life_used_fraction, `${row.name} final used`);
      close(final.mkt_c, want.mkt_c, `${row.name} final MKT`);
      close(final.effective_temp_c, want.effective_temp_c, `${row.name} effective`);
      close(final.current_af, want.current_af, `${row.name} AF now`);
      close(
        final.hours_to_min_potency_at_current_temp,
        want.hours_to_min_potency_at_current_temp,
        `${row.name} hours to min`,
      );
      expect(final.status).toBe(want.status);
      expect(final.below_min_potency).toBe(want.below_min_potency);
      expect(final.samples_seen).toBe(want.samples_seen);
      expect(final.samples_excluded).toBe(want.samples_excluded);
    }
  });
});

describe("reference profile: worked examples from the team document", () => {
  const c = reference.meta.constants as ProductConstants;
  const checks = reference.document_checks;

  it("matches every rounded document check", () => {
    expect(checks.length).toBe(6);
    for (const check of checks) {
      const af = accelerationFactor(check.temp_c, c);
      const tau = af * check.hours;
      const value =
        check.quantity === "af"
          ? af
          : check.quantity === "tau_eq_h"
            ? tau
            : check.quantity === "shelf_life_used_percent"
              ? shelfLifeUsedFraction(tau, c) * 100
              : Number.NaN;
      expect(Number.isNaN(value), `unknown quantity ${check.quantity}`).toBe(false);
      const factor = 10 ** check.rounding_decimals;
      expect(Math.round(value * factor) / factor, check.description).toBe(check.expected_rounded);
    }
  });
});

describe("the mirror's own guards", () => {
  const c = active.meta.constants as ProductConstants;

  it("rejects bad numbers the way the Python code does", () => {
    expect(() => accelerationFactor(Number.NaN, c)).toThrow(RangeError);
    expect(() => accelerationFactor(-300, c)).toThrow(RangeError);
    expect(() => equivalentReferenceTimeH([5], [-1], c)).toThrow(RangeError);
    expect(() => equivalentReferenceTimeH([5, 6], [1], c)).toThrow(RangeError);
    expect(() => potencyFromTauEq(-1, c)).toThrow(RangeError);
    expect(() => timeWeightedMktC([], [], c)).toThrow(RangeError);
    expect(() => timeWeightedMktC([5], [0], c)).toThrow(RangeError);
    expect(() => hoursToMinPotencyAtTemp(Number.POSITIVE_INFINITY, 5, c)).toThrow(RangeError);
  });

  it("is exactly 1 at the reference temperature, and potency is 1 at zero time", () => {
    expect(accelerationFactor(c.T_ref_c, c)).toBeCloseTo(1, 14);
    expect(potencyFromTauEq(0, c)).toBe(1);
  });

  it("tracker refuses time going backwards and can be reset", () => {
    const tracker = new PotencyTracker(c);
    tracker.update(0, 5);
    tracker.update(600, 5);
    expect(() => tracker.update(300, 5)).toThrow(RangeError);
    tracker.reset();
    expect(tracker.update(0, 5).samples_seen).toBe(1);
  });
});
