// TypeScript mirror of edge/potency.py, for Chapter 1's scrub only. It reproduces the Python code
// line by line (plain left-to-right sums, same constants, same integration rule) and is tested
// against BOTH shared vector files. It is NOT a place for planner maths: the front end never
// computes planner numbers. Potency here is a model output for an imaginary product.

export interface ProductConstants {
  Ea_over_R: number;
  T_ref_c: number;
  tau_max_h: number;
  P_min: number;
  hard_limit_low_c: number;
  hard_limit_high_c: number;
  hard_limit_consecutive_samples: number;
}

const KELVIN_OFFSET = 273.15;
const SECONDS_PER_HOUR = 3600.0;

export function kRefPerH(c: ProductConstants): number {
  return Math.log(1.0 / c.P_min) / c.tau_max_h;
}

function kelvin(tempC: number): number {
  if (typeof tempC !== "number" || !Number.isFinite(tempC)) {
    throw new RangeError(`temperature must be a finite number (got ${String(tempC)})`);
  }
  const k = tempC + KELVIN_OFFSET;
  if (k <= 0) throw new RangeError(`absolute temperature must be positive (got ${tempC} C)`);
  return k;
}

function checkDt(dtH: number): void {
  if (typeof dtH !== "number" || !Number.isFinite(dtH)) {
    throw new RangeError(`time step must be a finite number (got ${String(dtH)})`);
  }
  if (dtH < 0) throw new RangeError(`time step must not be negative (got ${dtH} h)`);
}

/** AF(T) = exp((Ea/R) * (1/T_ref_K - 1/T_K)). */
export function accelerationFactor(tempC: number, c: ProductConstants): number {
  const tRefK = c.T_ref_c + KELVIN_OFFSET;
  return Math.exp(c.Ea_over_R * (1.0 / tRefK - 1.0 / kelvin(tempC)));
}

/** tau_eq = sum AF(T_i) * dt_i, hours at the reference temperature. */
export function equivalentReferenceTimeH(
  tempsC: readonly number[],
  dtsH: readonly number[],
  c: ProductConstants,
): number {
  if (tempsC.length !== dtsH.length) {
    throw new RangeError(`tempsC and dtsH must have the same length (got ${tempsC.length} and ${dtsH.length})`);
  }
  let total = 0.0;
  for (let i = 0; i < tempsC.length; i++) {
    checkDt(dtsH[i]);
    total += accelerationFactor(tempsC[i], c) * dtsH[i];
  }
  return total;
}

/** P = exp(-k_ref * tau_eq). */
export function potencyFromTauEq(tauEqH: number, c: ProductConstants): number {
  if (!Number.isFinite(tauEqH) || tauEqH < 0) {
    throw new RangeError(`tauEqH must be a finite number >= 0 (got ${tauEqH})`);
  }
  return Math.exp(-kRefPerH(c) * tauEqH);
}

/** tau_eq / tau_max. Multiply by 100 for percent. */
export function shelfLifeUsedFraction(tauEqH: number, c: ProductConstants): number {
  if (!Number.isFinite(tauEqH) || tauEqH < 0) {
    throw new RangeError(`tauEqH must be a finite number >= 0 (got ${tauEqH})`);
  }
  return tauEqH / c.tau_max_h;
}

/** Running sum of dt * exp(a), a = -(Ea/R)/T_K, kept as sum * exp(max_a) to avoid underflow. */
class MktAccumulator {
  maxA = -Infinity;
  scaledSum = 0.0;
  durationH = 0.0;

  add(tempC: number, dtH: number, eaOverR: number): void {
    checkDt(dtH);
    if (dtH === 0.0) return;
    const a = -eaOverR / kelvin(tempC);
    if (a > this.maxA) {
      this.scaledSum = this.scaledSum * Math.exp(this.maxA - a) + dtH;
      this.maxA = a;
    } else {
      this.scaledSum += dtH * Math.exp(a - this.maxA);
    }
    this.durationH += dtH;
  }

  mktC(eaOverR: number): number | null {
    if (this.durationH <= 0.0) return null;
    const logMean = this.maxA + Math.log(this.scaledSum / this.durationH);
    return eaOverR / -logMean - KELVIN_OFFSET;
  }

  copy(): MktAccumulator {
    const other = new MktAccumulator();
    other.maxA = this.maxA;
    other.scaledSum = this.scaledSum;
    other.durationH = this.durationH;
    return other;
  }
}

/** Mean kinetic temperature (C), weighted by time. Throws for empty input or zero total time. */
export function timeWeightedMktC(
  tempsC: readonly number[],
  dtsH: readonly number[],
  c: ProductConstants,
): number {
  if (tempsC.length !== dtsH.length) {
    throw new RangeError(`tempsC and dtsH must have the same length (got ${tempsC.length} and ${dtsH.length})`);
  }
  if (tempsC.length === 0) throw new RangeError("cannot compute a mean kinetic temperature from empty input");
  const acc = new MktAccumulator();
  for (let i = 0; i < tempsC.length; i++) acc.add(tempsC[i], dtsH[i], c.Ea_over_R);
  const result = acc.mktC(c.Ea_over_R);
  if (result === null) throw new RangeError("total duration is zero; a mean kinetic temperature needs elapsed time");
  return result;
}

/** Hours until potency reaches P_min if the box stayed at tempC from now on (derived helper). */
export function hoursToMinPotencyAtTemp(tauEqH: number, tempC: number, c: ProductConstants): number {
  if (!Number.isFinite(tauEqH) || tauEqH < 0) {
    throw new RangeError(`tauEqH must be a finite number >= 0 (got ${tauEqH})`);
  }
  const remaining = Math.max(0.0, c.tau_max_h - tauEqH);
  return remaining / accelerationFactor(tempC, c);
}

export type TrackerStatus = "ok" | "suspect" | "excursion_confirmed";

export interface PotencyState {
  t_s: number;
  tau_eq_h: number;
  potency: number;
  shelf_life_used_fraction: number;
  mkt_c: number | null;
  effective_temp_c: number | null;
  current_af: number | null;
  hours_to_min_potency_at_current_temp: number | null;
  status: TrackerStatus;
  below_min_potency: boolean;
  samples_seen: number;
  samples_excluded: number;
}

interface Pending {
  actualTempC: number;
  heldTempC: number | null;
  dtH: number;
}

/** Streaming tracker with the suspect-reading rule of edge/potency.py (amendment A5). */
export class PotencyTracker {
  private tauEqH = 0.0;
  private mkt = new MktAccumulator();
  private pending: Pending[] = [];
  private prevTS: number | null = null;
  private lastValidC: number | null = null;
  private consecutiveOut = 0;
  private excludedCommitted = 0;
  private seen = 0;
  private status: TrackerStatus = "ok";
  private effectiveC: number | null = null;

  constructor(private readonly c: ProductConstants) {}

  reset(): void {
    this.tauEqH = 0.0;
    this.mkt = new MktAccumulator();
    this.pending = [];
    this.prevTS = null;
    this.lastValidC = null;
    this.consecutiveOut = 0;
    this.excludedCommitted = 0;
    this.seen = 0;
    this.status = "ok";
    this.effectiveC = null;
  }

  update(tS: number, tempC: number): PotencyState {
    const c = this.c;
    kelvin(tempC);
    if (!Number.isFinite(tS)) throw new RangeError(`time must be finite (got ${tS})`);
    if (this.prevTS !== null && tS < this.prevTS) {
      throw new RangeError(`time went backwards (${tS} s after ${this.prevTS} s)`);
    }
    const dtH = this.prevTS === null ? 0.0 : (tS - this.prevTS) / SECONDS_PER_HOUR;
    this.prevTS = tS;
    this.seen += 1;

    const outside = tempC < c.hard_limit_low_c || tempC > c.hard_limit_high_c;
    if (!outside) {
      this.commitPending(false);
      this.accept(tempC, dtH);
      this.consecutiveOut = 0;
      this.status = "ok";
    } else {
      this.consecutiveOut += 1;
      if (this.consecutiveOut < c.hard_limit_consecutive_samples) {
        this.pending.push({ actualTempC: tempC, heldTempC: this.lastValidC, dtH });
        this.effectiveC = this.lastValidC;
        this.status = "suspect";
      } else {
        this.commitPending(true);
        this.accept(tempC, dtH);
        this.status = "excursion_confirmed";
      }
    }
    return this.snapshot();
  }

  private accept(tempC: number, dtH: number): void {
    this.tauEqH += accelerationFactor(tempC, this.c) * dtH;
    this.mkt.add(tempC, dtH, this.c.Ea_over_R);
    this.lastValidC = tempC;
    this.effectiveC = tempC;
  }

  private commitPending(useActual: boolean): void {
    for (const item of this.pending) {
      const tempC = useActual ? item.actualTempC : item.heldTempC;
      if (tempC !== null) {
        this.tauEqH += accelerationFactor(tempC, this.c) * item.dtH;
        this.mkt.add(tempC, item.dtH, this.c.Ea_over_R);
      }
      if (!useActual) this.excludedCommitted += 1;
    }
    this.pending = [];
  }

  snapshot(): PotencyState {
    const c = this.c;
    let tau = this.tauEqH;
    let mkt = this.mkt;
    if (this.pending.length > 0) {
      mkt = mkt.copy();
      for (const item of this.pending) {
        if (item.heldTempC !== null) {
          tau += accelerationFactor(item.heldTempC, c) * item.dtH;
          mkt.add(item.heldTempC, item.dtH, c.Ea_over_R);
        }
      }
    }
    const potency = potencyFromTauEq(tau, c);
    const eff = this.effectiveC;
    return {
      t_s: this.prevTS === null ? 0.0 : this.prevTS,
      tau_eq_h: tau,
      potency,
      shelf_life_used_fraction: shelfLifeUsedFraction(tau, c),
      mkt_c: mkt.mktC(c.Ea_over_R),
      effective_temp_c: eff,
      current_af: eff === null ? null : accelerationFactor(eff, c),
      hours_to_min_potency_at_current_temp: eff === null ? null : hoursToMinPotencyAtTemp(tau, eff, c),
      status: this.status,
      below_min_potency: potency < c.P_min,
      samples_seen: this.seen,
      samples_excluded: this.excludedCommitted + this.pending.length,
    };
  }
}
