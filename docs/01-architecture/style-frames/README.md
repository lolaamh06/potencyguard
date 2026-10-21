# style-frames

- What lives here: Phase F1 static pages (prologue, futures, Control Room, font comparison), shared tokens, self-hosted fonts and the script that generates their data.
- Filled in by: Phase F1. Later frontend phases replace these with the real build.
- Finding things: serve this folder with `python -m http.server 8809 --bind 127.0.0.1` (the pages fetch JSON, so file:// will not work), then open `frame-1-prologue.html`, `frame-2-futures.html`, `frame-3-control-room.html` or `fonts-compare.html`.

- `generate_data.py` writes `data/*.json` from the project's own code (read-only use). The key it signs with is TEST ONLY and derived inside the script.
- `fonts/` holds Latin WOFF2 files under SIL OFL 1.1; licence texts and `manifest.json` are alongside.
- The globe, vial and all controls are styling placeholders. Everything is synthetic and illustrative.
