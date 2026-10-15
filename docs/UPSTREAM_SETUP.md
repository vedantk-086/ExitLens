# Upstream Setup and Preservation

The competition's starter is [`rishrek/LinkWatch`](https://github.com/rishrek/LinkWatch). It is a real Python CLI project with its own source, tests, packaging files, `README.md`, and MIT license. ExitLens must be added to a fork of this starter, not substituted for it.

## Recommended path

1. In GitHub, use **Fork** on the official repository so your submission remains a true fork.
2. Clone your own fork locally.
3. From the extracted ExitLens scaffold, run the bootstrap script and pass the path of your local fork:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -RepoPath "C:\work\your-linkwatch-fork"
   ```

4. The script verifies that the target looks like LinkWatch, backs up its existing root README to `docs/upstream/README-LinkWatch.md`, overlays ExitLens documentation and empty implementation directories, and appends ignore rules without replacing the original `.gitignore`.
5. It deliberately does **not** alter or delete LinkWatch's Python source, existing tests, `pyproject.toml`, root license, Dockerfile, Makefile, requirements or `sites.toml`.
6. Inspect `git diff` and `git status`; commit the scaffold before asking an agent to implement code.

The script will not clone upstream automatically: this prevents accidentally turning an unrelated local clone into a submission repository. Always fork the official repository on GitHub, clone your own fork, and pass that local path using `-RepoPath`. Verify `git remote -v` points to your fork as `origin`; optionally add `https://github.com/rishrek/LinkWatch.git` as the `upstream` remote. The script never pushes code or creates a GitHub fork.

## Preservation rules

- Do not replace or merge the upstream `pyproject.toml` with ExitLens dependencies. ExitLens has its own `exitlens_app/backend/requirements.txt`.
- Do not replace upstream `requirements.txt`; it belongs to LinkWatch.
- Keep upstream tests runnable from the root as its own acceptance baseline.
- The default ExitLens scanner exclusion must include `exitlens_app`, `reports`, `.git`, virtual environments, caches and `node_modules` so it does not scan itself.
- Keep generated output under `reports/exitlens/`, not mixed into upstream source folders.
