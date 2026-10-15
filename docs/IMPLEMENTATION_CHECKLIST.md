# Implementation Checklist

This is the single implementation order for ExitLens. The scaffold contains requirements and directory placeholders only; check an item only after code exists and the specified evidence/test has been recorded.

## Stage 0 — upstream and scope

- [ ] Fork the organizer target `rishrek/LinkWatch` using GitHub and clone your own fork.
- [ ] Keep all original LinkWatch source, tests, root metadata and MIT license; preserve the original upstream README under `docs/upstream/` when changing the root README.
- [ ] Confirm the checkout is running under Python 3.12 or 3.13 as required by the event/target; do not use Python 3.14 for LinkWatch.
- [ ] Run upstream tests before modifications and record the actual command/output.
- [ ] Confirm the selected event policy; default to local Gemma 4 via Ollama. Do not use paid API/cloud inference unless organizers explicitly approve it.

## Stage 1 — contract and skeleton

- [ ] Agree the public Pydantic schemas and exact service interfaces before dependent modules are implemented.
- [ ] Implement FastAPI entry point, health endpoint, configuration, request validation, standard error model and API route skeleton.
- [ ] Export OpenAPI from the running FastAPI app to `contracts/openapi.json`; do not hand-author fake generated types.
- [ ] Add focused unit tests and CI checks for the new project layer.

## Stage 2 — deterministic repository intelligence

- [ ] Validate local paths and public HTTPS Git URLs; do not execute manifest code or hooks.
- [ ] Parse supported Python dependency manifests/lockfiles and report unsupported/dynamic constructs.
- [ ] Map distributions to imports where possible, record file/line evidence and declare mapping uncertainty.
- [ ] Apply versioned, explainable maintenance-risk rules with stable IDs.
- [ ] Test path bounds, excluded directories, symlink escape rejection and evidence references.

## Stage 3 — Gemma 4 migration recommendations

- [ ] Validate actual local Ollama/model tag and a real short inference; record exact tag, provider method and prompt version.
- [ ] Send Gemma only bounded repository-specific evidence snippets, not the full repository or secrets.
- [ ] Validate structured output against the shared Pydantic model; reject unsupported paths and unknown evidence IDs.
- [ ] Label model output as recommendation, never as observation or execution proof.
- [ ] Test provider unavailable, timeout, malformed response, no candidate and partial/uncertain response.

## Stage 4 — verification and comparison

- [ ] Detect a server-defined, allow-listed test profile without running arbitrary project code during discovery.
- [ ] Require explicit human approval before test execution.
- [ ] Keep network off by default, use a disposable workspace, bounded timeout/logs and a restricted environment.
- [ ] Record actual baseline and replacement results distinctly; skip replacement if there is no reviewed change set or feasible environment.
- [ ] Compare results carefully, preserving baseline failures, environment differences and unresolved gaps.

## Stage 5 — capsule

- [ ] Assemble one canonical typed capsule object per analysis.
- [ ] Include every flagged dependency and all nine sections per dependency.
- [ ] Validate all evidence references and provenance labels.
- [ ] Render JSON and Markdown from the same object and test content parity.
- [ ] Persist run state/artifacts atomically; keep generated `reports/exitlens/` out of source control.

## Stage 6 — frontend integration

- [ ] Build a real React + Vite + TypeScript maintainer workbench (not a static mock or chat-only UI).
- [ ] Wire every displayed state to the backend API; implement loading, success, empty, partial/warning, and error states.
- [ ] Render inventory, source evidence, all nine capsule sections, verification approval/results and both downloads.
- [ ] Confirm no fake findings, sample statistics or fake progress appear in production.
- [ ] Verify keyboard accessibility, readable layout and responsive behavior.

## Stage 7 — end-to-end acceptance

- [ ] Fresh scan the actual LinkWatch checkout; no hard-coded dependency names/counts/findings.
- [ ] Verify scan data survives Gemma unavailability with an honest warning.
- [ ] Exercise every flagged dependency through recommendation outcome and capsule record.
- [ ] Exercise at least one safe baseline test where feasible; record skipped replacement checks honestly.
- [ ] Check health, job polling, inventory/detail, recommendation retry, verification and JSON/Markdown downloads end to end.
- [ ] Create a reproducible demonstration and gather actual screenshots/log excerpts; never fabricate test output.
- [ ] Confirm the public GitHub fork, meaningful commits, license, setup docs, required presentation, and submission instructions.
