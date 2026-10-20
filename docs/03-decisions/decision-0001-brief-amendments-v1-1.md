# Decision 0001: Brief amendments v1.1

Date: 2026-10-20

Fourteen small decisions that change or extend the master brief. The full text is at the end of `docs/00-project-brief/master-brief.md`.

- **A1, git rule.** The AI builder never runs commands that change git history. It prints the commands and the team lead chooses to run them. Reason: the team lead stays in control of what is saved and pushed.
- **A2, unrounded test values.** Tests compare against exact formula results, and the brief's rounded numbers must match once rounded. Reason: rounded numbers in tests would hide small errors.
- **A3, two layers of CVaR testing.** One exact test on small lists of losses, one approximate test on the random simulation. Reason: random simulations can only be checked approximately, so the exact test pins down the formula.
- **A4, signed record fields.** The list of fields in every signed record is fixed. Reason: everyone knows exactly what is protected, and the dashboard can show provenance from it.
- **A5, two readings before quarantine.** One extreme reading is only marked suspect; two in a row trigger quarantine. Reason: a single noisy reading should not stop a shipment.
- **A6, time-weighted MKT.** Mean kinetic temperature weights each reading by how long it lasted. Reason: readings are not always evenly spaced.
- **A7, signing library.** The `cryptography` package signs records (Ed25519), and all Python packages are pinned to exact versions. Reason: a well-known library and repeatable installs.
- **A8, no title card.** No banner or title card on the dashboard or recordings, but the Provenance drawer stays. Reason: a clean look without hiding where data comes from.
- **A9, a `shared` package.** A fifth Python package holds config loading and common types. Reason: avoids duplicating code across packages.
- **A10, frontend vision is binding.** The design document is moved into `docs/01-architecture/` and all frontend phases must follow it. Reason: one agreed direction for the dashboard.
- **A11, new roadmap.** Backend phases 1 to 6 and frontend phases F1 to F6 can run in parallel, and the slides keep priority. Reason: the frontend is a big part of the pitch and needs its own track.
- **A12, extra folders.** Added `docs/06-prompts/`, `shared/test-vectors/` and a Vite React dashboard. Reason: keeps prompts archived and lets Python and TypeScript share the same test numbers.
- **A13, tooling awareness.** This phase only lists available tools; later frontend phases should use a design skill and browser screenshots if present. Reason: nothing is installed without a decision.
- **A14, UI honesty rules.** The honesty rules for the dashboard carry the same force as the brief's. Reason: what is on screen must never overstate what is real.
