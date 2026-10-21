# dashboard

- What lives here: the cinematic Story and Control Room front end (Vite + React + TypeScript + three.js). Phase F2 built the foundation (app shell, scroll rig, 3D globe, quality governor, mode adapter, TypeScript potency mirror). Phase F3 built the Story: the Prologue and Chapters 1 to 7 in `src/story/`, with Control Room panels still to come (F4 and F5).
- Run it: `npm run dev` (serves http://127.0.0.1:5173). `npm run build` and `npm test` check the code. Open `/?tier=high`, `/?mode=replay#/control-room` and so on.
- URL options: `?mode=story|replay|live` (data source, default story), `?tier=high|medium|low|fallback2d` (forces a quality tier). Keys: `?` shows the list; `Q` quality, `D` performance numbers, `M` reduced motion, `G` Story, `C` Control Room, Space and arrows to move.
- Source: `src/app` (shell), `src/scroll` (scroll rig and chapter table), `src/globe` (the globe), `src/quality` (governor), `src/data` (adapter and validation), `src/potency` (TypeScript potency mirror, tested against `shared/test-vectors/`), `src/theme` (tokens, fonts).
- Data: `public/replay/` is written by `python scripts/export_replay.py`; `public/story/` and `src/data/bundled/chapter1.json` by `python scripts/export_story.py`; `public/globe/` by `python scripts/make_land_mask.py` (README there names the source and licence). Fonts in `public/fonts/` are SIL OFL 1.1.
- Live mode reads the backend (`python -m backend serve`) through the dev proxy `/api`, read-only.
- OneDrive note: `node_modules` is a junction to `%LOCALAPPDATA%\potencyguard\dashboard-node_modules\node_modules`, so packages are not synced.
- Warning: a plain `npm install` or `npm ci` inside this folder REPLACES the junction with a real folder inside OneDrive. To add or change a package, follow docs/03-decisions/decision-0011-frontend-foundation.md section 1: install in `%LOCALAPPDATA%\potencyguard\dashboard-node_modules`, copy `package.json` and `package-lock.json` back, then check the junction.
