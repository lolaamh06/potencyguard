# config

- What lives here: Tunable parameters in YAML (product parameters, thresholds).
- Filled in by: Phase 0 adds product_default.yaml; later phases add more.
- Finding things: Every number you might want to change is in a YAML file here.

## Product profiles

- `product_default.yaml` is the ACTIVE profile and also holds the box simulator and free-run settings. Its kinetic constants (Ea/R 15000 K, shelf life 8760 h) are an illustrative heat-sensitive biologic profile: placeholder, not sourced [SOURCE NEEDED]; replace with the manufacturer's stability data.
- `product_team_document.yaml` is the REFERENCE profile (Ea/R 10000 K, shelf life 17520 h), taken from the team document and not independently verified by us [SOURCE NEEDED]. It keeps the document's worked examples verifiable. A test checks that every other key matches the active file.
- Load either one by path: `load_product_config("config/product_team_document.yaml")`.
