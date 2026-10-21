# config

- What lives here: Tunable parameters in YAML (product parameters, thresholds).
- Filled in by: Phase 0 adds product_default.yaml; later phases add more.
- Finding things: Every number you might want to change is in a YAML file here.

## Product profiles

- `product_default.yaml` is the ACTIVE profile and also holds the box simulator and free-run settings. Its kinetic constants (Ea/R 15000 K, shelf life 8760 h) are an illustrative heat-sensitive biologic profile: placeholder, not sourced [SOURCE NEEDED]; replace with the manufacturer's stability data.
- `product_team_document.yaml` is the REFERENCE profile (Ea/R 10000 K, shelf life 17520 h), taken from the team document and not independently verified by us [SOURCE NEEDED]. It keeps the document's worked examples verifiable. A test checks that every other key matches the active file.
- Load either one by path: `load_product_config("config/product_team_document.yaml")`.

## Twin and detector settings (Phase 3)

- `twin_calibrated.yaml`: the thermal twin fitted from `data/calibration/` (time constant, cooling depression, residual spread). Simulation only; regenerate with `python -m edge calibrate`.
- `detectors.yaml`: settings of the four tamper detectors. Every value is a placeholder [SOURCE NEEDED]; the CUSUM values come from the sweep in `scripts/evaluate_detectors.py`.

## Phase 3B additions

- `product_default.yaml`: `door_max_power_w` (120 W): the largest door power the injectable `open_door` command accepts and the largest any shipped scenario uses. Placeholder, not sourced [SOURCE NEEDED].
- `detectors.yaml`: `heat_allowance_c` now documents its meaning (the largest sudden warming of the box that an unseen heat load can cause in one sample interval) and its derivation (`box_R_th_k_per_w * door_max_power_w` = 60 K; a test keeps the value between 1 and 1.5 times that). New keys `ood_window_samples`, `ood_gain_margin`, `ood_gain_band_low`, `ood_gain_band_high`, `ood_sustained_samples`, `ood_max_gain_se` (the twin-out-of-date self-check, tuned on the training seeds only, see `docs/02-phase-reports/phase-03b-evaluation.md`) and `trust_lookback_samples` (how far before the first evidence the worst-case bound starts). All are placeholders, not sourced [SOURCE NEEDED].
