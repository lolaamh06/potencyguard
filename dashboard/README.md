# dashboard

- What lives here: the cinematic Story and Control Room (Phases F1 to F6). Today it holds only a throwaway WebGL smoke test (Vite + React + TypeScript) that checks smooth 3D and scrolling on this laptop.
- Run it: `npm run dev`, then open http://localhost:5173. Scroll, and press Q to cycle the quality tier. `npm run build` and `npm test` check the code.
- Source code is in `src/smoke/`. Quality-tier logic is in `qualityTier.ts`, with tests next to it.
- OneDrive note: `node_modules` is a junction to `%LOCALAPPDATA%\potencyguard\dashboard-node_modules\node_modules`, so the packages are not synced. The target folder itself must be named `node_modules`, otherwise Node cannot resolve packages.
- Warning: npm install or npm ci REPLACES the junction with a real folder inside OneDrive. Only run them when a phase says so, then follow the recovery steps. A plain `npm install` replaces the junction with a real folder. To add or change packages, run `npm install`, then move the new `node_modules` folder to the target above and re-create the junction with `cmd /c mklink /J`.
