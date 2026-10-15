# Start Here — ExitLens Scaffold

This is a requirements-first starter package, not a finished/runnable application. It deliberately contains **no backend implementation and no frontend page code** yet.

## First action

Use a true GitHub fork of [`rishrek/LinkWatch`](https://github.com/rishrek/LinkWatch) for the hackathon submission. Do not submit this ZIP as if it were the upstream fork.

From PowerShell in this extracted folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -RepoPath "C:\work\your-linkwatch-fork"
```

Pass the path to a local clone of your GitHub fork. The script requires an existing fork checkout and refuses to create an unrelated upstream clone, so the submission remains rooted in the required GitHub fork.

## Then read in this order

1. [`README.md`](README.md) — full project intent and hackathon acceptance contract.
2. [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — frozen API/status/capsule contract.
3. [`exitlens_app/backend/README.md`](exitlens_app/backend/README.md) — complete backend requirements.
4. [`exitlens_app/frontend/README.md`](exitlens_app/frontend/README.md) — complete frontend requirements.
5. [`docs/IMPLEMENTATION_CHECKLIST.md`](docs/IMPLEMENTATION_CHECKLIST.md) — implementation order and verification gates.
6. [`docs/UPSTREAM_SETUP.md`](docs/UPSTREAM_SETUP.md) — preservation and Git workflow.

## Important

- This archive has a scaffold folder but does not include original LinkWatch source or its `.git` history. Bootstrap merges the scaffold into a real clone, preserving upstream source and license.
- The app modules are placeholders. Do not claim an endpoint or UI is complete because its directory exists.
- Do not put secrets into either `.env.example`; create a local `.env` only when implementation starts.
- Keep inference local through Ollama/Gemma 4 unless organizers explicitly approve a hosted provider under event rules.
