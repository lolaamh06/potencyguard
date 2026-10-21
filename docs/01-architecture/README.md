# 01-architecture

- What lives here: How the parts connect; the frontend vision; design system (filled in later).
- Filled in by: Phase 0 holds the frontend vision; F1 and later add the design system and diagrams.
- Finding things: Open frontend-vision.md first.

- `signed-record-format.md` (Phase 4): the exact byte rules for signed records.
- `api.md` (Phase 6): the backend endpoints and PowerShell examples. No authentication in this phase.
- `design-system.md` (F1): colour, type, spacing, motion tokens and the font proposal. Binding tokens are in `style-frames/tokens.css`.
- `storyboard.md` (F1): scenes, copy, timing and the Control Room wireframe. Items marked PROPOSE await the decision-maker.
- `style-frames/` (F1): four static pages, the data generator and the self-hosted fonts. See its README.
- Phase F2 (frontend foundation) is documented in `docs/02-phase-reports/phase-f2-report.md` and `docs/03-decisions/decision-0011-frontend-foundation.md`. The code is in `dashboard/src/`.
- Phase F3 (the Story) is documented in `docs/02-phase-reports/phase-f3-report.md`; the chapter components are in `dashboard/src/story/`, the 3D stage in `dashboard/src/globe/Stage.tsx`.
