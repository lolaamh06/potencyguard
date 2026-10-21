# Decision 0011: frontend foundation (junction procedure, dependencies, quality governor)

Status: decided and built in Phase F2. Everything the app shows is an illustrative journey on a synthetic box. Signing protects records after signing and does not stop a lie at the sensor (A18); nothing in the front end suggests otherwise.

## 1. The node_modules junction procedure

`dashboard/node_modules` is a junction to `%LOCALAPPDATA%\potencyguard\dashboard-node_modules\node_modules`, so packages are not synced by OneDrive. A plain `npm install` inside `dashboard/` would replace the junction with a real folder. Procedure used and to be used for every dependency change:

1. Look at the junction (`cmd /c "dir /AL"` in `dashboard/`; `Get-Item dashboard\node_modules` shows `LinkType Junction` and its target).
2. Work in the junction's PARENT, `%LOCALAPPDATA%\potencyguard\dashboard-node_modules`, which already holds the `node_modules` folder the junction points at. Copy `dashboard/package.json` and `package-lock.json` there.
3. Run `npm install --save-exact <package>@<version>` there. The packages land in the same `node_modules` the junction points to.
4. Copy `package.json` and `package-lock.json` back into `dashboard/`.
5. Check again: the junction is still a junction and no real `node_modules` folder exists in OneDrive.

Result in F2: one change (vite 8.3.4 to 8.3.5). Junction intact before and after. All other packages were already at the latest version (`npm view`), exact-pinned.

## 2. Dependencies (all exact, no ^ or ~)

react 19.3.1, react-dom 19.3.1, three 0.186.1, @react-three/fiber 9.8.2, @react-three/drei 10.7.9, @react-three/postprocessing 3.2.1, postprocessing 6.39.5, gsap 3.15.0, lenis 1.3.27, zustand 5.0.15, d3-scale 4.0.2, d3-shape 3.2.0; dev: vite 8.3.5, @vitejs/plugin-react 6.1.2, typescript 7.0.2, vitest 5.0.5, @types/react 19.3.0, @types/react-dom 19.3.0, @types/three 0.186.0, @types/d3-scale 4.0.9, @types/d3-shape 3.2.0. d3-scale and d3-shape are installed for later chart phases and not used yet. No test-DOM library was needed: the logic under test is pure and the screen was checked in a real browser.

## 3. Quality governor design

- Four tiers: high, medium, low, fallback2d. A tier sets pixel-ratio cap, bloom and vignette (high and medium only), dot and star counts and grain.
- The decision logic is a pure function (`quality/governor.ts`): the render loop sums frame times in windows of 60 frames; a window averaging over 25 ms (40 fps) is bad; three bad windows in a row step down one tier; the first two windows after start or after a change are ignored (shader compile); a good window resets the streak. It never steps up and never chooses the 2D fallback by itself.
- A tier forced with `?tier=` or chosen with Q is locked: the governor leaves it alone. No WebGL gives the 2D fallback.
- Own governor instead of drei's PerformanceMonitor: its decision is a pure function and so can be unit tested, and its rule (never up) is explicit.
- Render numbers come from `gl.info` with `autoReset` off and a manual reset each frame, so draw calls and triangles cover every pass of the frame, including post-processing.

## 4. Other choices

- Hash routing (`#/story`, `#/control-room`), no router library.
- Live mode reads the backend through a same-origin proxy (`/api` to 127.0.0.1:8765, set in `vite.config.ts` for dev and preview), so the page makes no cross-origin request and the backend needs no CORS change. Live is read-only (`GET /health`, `GET /shipments`) and falls back to replay with a calm message.
- Chapter on screen is decided by the middle of the viewport, so a short last chapter stays reachable.
- The old Phase 0 smoke test under `dashboard/src/smoke/` is left in place, unused (see the report).
