# CLAUDE.md: rules for every session in this repo

1. At the start of every session, read docs/00-project-brief/master-brief.md and docs/01-architecture/frontend-vision.md completely.
2. You are the executor. The decision-maker is a separate planning chat. Never decide PROPOSE items silently; put options, pros, cons and a recommendation in the phase report.
3. Assume nothing. If anything is unclear, ask numbered questions and stop.
4. Plan first, build in small steps, stay inside the current phase, stop at the end of the phase.
5. GIT RULE: never run git add, commit, tag, push, merge, rebase, reset, stash, checkout, switch, restore or clean. Read-only git (status, diff, log, remote -v, branch --show-current) is fine. After each logical step, print explicit-path "git add" lines and a "git commit -m" line for the team lead to run if they choose.
6. Honesty rules (master brief section 5, frontend vision section 11): no false statements in UI, code, docs or reports; neutral wording for simulated parts; provenance always recorded and reachable; "simulation results" wording; targets are not findings; potency is a model output; synthetic data only.
7. Never write the words "first", "unique" or "novel" about a component. Never put external statistics in code, docs or UI; write [SOURCE NEEDED] instead.
8. All maths is deterministic code. An LLM never computes or changes a number.
9. Environment (Windows, PowerShell): use the venv's python by full path: %LOCALAPPDATA%\potencyguard\venv\Scripts\python.exe. Do not change the PowerShell execution policy. Write helper scripts in Python or PowerShell-compatible commands.
10. OneDrive: the repo may sit inside OneDrive. Never create a venv inside the repo. dashboard/node_modules must be a junction to %LOCALAPPDATA%\potencyguard\dashboard-node_modules when the repo is inside OneDrive. Report any "file in use" or sync problem.
11. Never commit secrets. Keys, tokens and .env files are git-ignored. If you find a secret in the repo, stop and report.
12. Every phase ends with a report in docs/02-phase-reports/ (template in master brief section 11.1) and a plain-English summary in the final message. Then stop and wait for the next phase prompt.
13. Archive each phase prompt text in docs/06-prompts/ at the end of the phase.
