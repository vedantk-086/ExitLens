# ExitLens Frontend — React + Vite + TypeScript

This README defines the frontend contract for ExitLens. The frontend is a maintainer-facing dependency-migration workbench. It must be visually deliberate, evidence-dense and fully connected to the FastAPI backend. It is **not** a static mock dashboard, a chat-only interface or a Streamlit wrapper.

> **Implementation status:** This is the frontend implementation specification. Build and verify the screens, API client and states before describing them as complete.

## 1. Product goal

A developer should be able to complete this entire user journey through the UI:

**Select LinkWatch → run a fresh scan → inspect a real flagged dependency → review Gemma 4's migration proposal → approve a feasible verification run → inspect actual outcomes and unresolved gaps → export the Dependency Exit Capsule as Markdown/JSON.**

The UI must read the backend's saved analysis/evidence. It must not hard-code dependency names, counts, risk levels, model responses, test statuses or capsule data. If a scan finds no flagged dependencies, show a useful empty state with scan coverage; never manufacture a risk for the demo.

## 2. Frontend stack and configuration

Recommended stack:

- React + Vite + TypeScript.
- Tailwind CSS with a small shared token system; shadcn/ui primitives where useful and kept visually consistent.
- `lucide-react` for restrained, consistent icons.
- Native `fetch` or one small typed API client; do not maintain duplicate state/data in several UI layers.
- Optional TanStack Query if already selected for polling/cache invalidation; keep it consistent across the whole app rather than partially mixing data approaches.

Do not introduce a second state-management framework unless the implementation needs it. The code should stay small and predictable within the hackathon timeline.

### Environment

`.env.example`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Only public frontend settings belong in `VITE_` variables. Never put model credentials, filesystem paths that should remain private, secrets, or provider tokens into Vite environment variables; values with the `VITE_` prefix are exposed to the browser bundle.

### Install and run (PowerShell)

Start the backend first, then in a second terminal:

```powershell
cd exitlens_app\frontend
npm install  # first scaffold install; commit package-lock.json, then use npm ci
Copy-Item .env.example .env
npm run dev -- --host 127.0.0.1
```

Open the local URL printed by Vite. Set the API base URL to `http://127.0.0.1:8000/api/v1` if needed. Use `npm run build` as a release check and `npm run lint`/`npm run typecheck` if those scripts are included in `package.json`.

## 3. API integration — must match the backend exactly

All API calls use `VITE_API_BASE_URL`. Keep endpoint paths and TypeScript response types in one place under `src/api/`. Do not embed URLs throughout page components.

| UI action | Method and path | UI behavior |
|---|---|---|
| Check backend/model status | `GET /health` | Show API status and model readiness separately. Model not ready is a warning, not “all systems operational.” |
| Submit a repository | `POST /analyses` | Send `repository.kind`, `repository.value`, optional `git_ref` and scan options; on `202`, save returned `analysis_id`. |
| Poll run | `GET /analyses/{analysis_id}` | Poll while status is active, with a modest interval/backoff; stop on completed, completed-with-warnings or failed. |
| Show inventory | `GET /analyses/{analysis_id}/dependencies` | Render backend results and filtering/sorting locally without altering evidence. |
| Open a dependency | `GET /analyses/{analysis_id}/dependencies/{dependency_id}` | Show the detailed record and linked evidence. |
| Retry recommendations | `POST /analyses/{analysis_id}/recommendations` | Send selected dependency IDs; show the response as queued/running until the backend updates status. |
| Start verification | `POST /analyses/{analysis_id}/verification` | Show the exact approved test profile, target and safety notes; require explicit user confirmation before submit. |
| Export JSON | `GET /analyses/{analysis_id}/capsule?format=json` | Download the backend's canonical capsule file. |
| Export Markdown | `GET /analyses/{analysis_id}/capsule?format=md` | Download the backend-rendered human-readable capsule. |

Do not add frontend-only routes or alter the shared endpoint contract without updating the backend and root README together.

### Types and data ownership

Create TypeScript types corresponding to the Pydantic schemas: `AnalysisStatus`, `DependencyRecord`, `RiskIndicator`, `UsageLocation`, `MigrationRecommendation`, `TestSuggestion`, `ExecutedTestResult`, `CompatibilityGap`, `OpenConcern`, `EvidenceReference` and `DependencyExitCapsule`.

The capsule's canonical per-dependency fields are:

1. `dependency_details`
2. `risk_indicators`
3. `usage_locations`
4. `proposed_replacement`
5. `migration_steps`
6. `suggested_tests`
7. `executed_test_results`
8. `compatibility_gaps`
9. `open_concerns_limitations`

The frontend must render all nine. Empty data needs explanatory states such as “No static usage located,” “No candidate identified,” “Not run,” or “Not assessed.” Do not omit sections merely because values are absent.

### Run status handling

Render the backend's run states exactly: `queued`, `validating_repository`, `scanning`, `mapping_usage`, `assessing_risk`, `generating_recommendations`, `ready_for_verification`, `verifying`, `completed`, `completed_with_warnings`, `failed`.

Test status labels must distinguish `PASSED`, `FAILED`, `ERROR`, `TIMED_OUT`, `SKIPPED` and `NOT_RUN`. `NOT_VERIFIED` is a state of a claim/candidate, not a successful test status. A recommendation with `candidate_validation_status=NOT_VERIFIED` must not receive a green verified badge.

## 4. Information architecture and screens

### A. Repository workspace

Purpose: start and monitor real scans.

- A clear repository input supporting a local path or allowed public HTTPS Git URL.
- LinkWatch shown as a convenient example/default only if that path is configured and valid on the backend host.
- Runtime/version check, repository revision (when available), analysis exclusions and model readiness.
- One primary “Analyze repository” action.
- An actual multi-stage progress component driven by backend status.
- Recent run list only if the backend provides it; do not show fake history.
- Useful error recovery for missing path, permission denied, unsupported repository layout, unavailable Gemma and failed clone.

The browser cannot read arbitrary local filesystem paths. The local desktop workflow works because the backend runs on the developer's machine and resolves the submitted path within configured allowed roots. Never imply that a browser can access the user's disk directly.

### B. Analysis overview and dependency inventory

Show compact factual summary counts supplied by the backend: dependencies discovered, flagged, recommendations available, checks passed/failed/skipped, and capsule completeness. Do not calculate a mysterious composite “health score.”

Inventory table columns:

- Dependency/package name.
- Declared and resolved version (show unknown when not available).
- Highest evidenced risk severity and rule labels.
- Manifest source.
- Number of static usage locations found.
- Recommendation status.
- Verification status.

Include search and filters by risk severity, recommendation state and verification state. Provide sorting with visible sort direction. Preserve all items; do not truncate the set of flagged dependencies to a few cards.

### C. Dependency detail and migration workbench

Sections or tabs, in this order:

1. **Observed details:** declarations, manifest location, version/metadata status and evidence links.
2. **Risk indicators:** rule ID, severity, explanation, source and evidence.
3. **Usage locations:** repository-relative path, line range, import/symbol and a bounded code excerpt where returned by the API.
4. **Gemma 4 recommendation:** candidate, rationale, API differences, evidence references and uncertainty.
5. **Migration steps:** numbered steps, files affected, expected change and human-review notes.
6. **Suggested tests:** goal, relation to usage and selected test profile.
7. **Executed results:** baseline versus replacement in separate sections, commands/profile IDs, statuses, durations, exit codes and bounded output.
8. **Compatibility gaps:** observed failures/differences and remaining unknowns.
9. **Open concerns:** unsupported metadata, skipped runs, model uncertainty and limitations.

Make it clear which content is observed and which came from Gemma 4. Use evidence IDs as links/popovers into the matching manifest/source location when feasible. Do not show arbitrary full source files; display small sanitized excerpts.

### D. Verification approval and results

Before a run, show:

- The dependency/candidate selected.
- The baseline and replacement test profiles the backend detected.
- Which workspace will be modified (must be a disposable copy).
- Whether the run may install dependencies or use the network (network is off by default).
- Timeout, expected duration if known, and the fact that project tests execute code.

Require explicit confirmation. After submission, display the real job status; do not show a spinner followed by presumed success. Present baseline/replacement records side by side only when profile/environment differences are disclosed. If a check is skipped, show the reason prominently.

### E. Capsule inspector and export

- Present an expandable capsule with the nine required sections per flagged dependency.
- Show capsule schema version, capsule/run IDs, generation time, repository revision, model ID/access method and coverage notes.
- Provide two clear download actions for JSON and Markdown.
- Disable export only if the backend says the artifact is unavailable; explain why.
- Display completeness/validation warnings from the server.
- The downloaded data must come from the backend endpoint. Do not build a separate frontend-only capsule that can drift from persisted evidence.

## 5. Visual direction — professional developer tooling, not AI slop

Use a restrained and information-first visual language:

- Light neutral canvas with dark slate text; one controlled blue/indigo primary accent.
- Amber for caution, red for observed failure/high-risk evidence, green for completed checks only, and neutral grey for unknown/not-run.
- A consistent spacing scale, type scale and border/radius system. Use typography and alignment rather than heavy drop shadows or decorative gradients to create hierarchy.
- Compact but readable tables, source references, code snippets and clear metadata.
- Use charts only when they communicate real backend counts or verified comparisons. No invented percentages, gauges or scores.
- Keep navigation predictable: Workspace, Analysis, Verification and Capsule. On a short hackathon, a sidebar plus a strong main content area is sufficient.
- Use one primary call-to-action per major state; confirmation dialogs for test execution and any action with side effects.

### Required states

Every page that loads remote data must include loading, successful, empty, partial/warning and error states. Also handle an offline API, a missing model, no at-risk candidates, no replacement candidate, no usage location, a failed baseline, a skipped replacement run and a failed capsule download.

Avoid:

- Hard-coded numbers or example findings inside production components.
- Fake logs/progress or AI “typing” animations presented as backend work.
- Multiple decorative cards that repeat the same metric.
- A chat interface as the primary product.
- Green success status when a request is only queued.
- Silent fallback to fixture data on API errors.

Fixtures may be used in component/unit tests only; production routes must display a proper error/empty state if the backend is unavailable.

## 6. Component and source structure

```text
exitlens_app/frontend/src/
├── api/
│   ├── client.ts             # base URL, JSON/error handling
│   ├── health.ts
│   ├── analyses.ts
│   ├── dependencies.ts
│   ├── verification.ts
│   └── capsules.ts
├── types/                    # shared API response types
├── components/
│   ├── app-shell/
│   ├── status-badge.tsx
│   ├── evidence-reference.tsx
│   ├── empty-state.tsx
│   ├── error-state.tsx
│   ├── data-table.tsx
│   └── code-excerpt.tsx
├── features/
│   ├── repository-workspace/
│   ├── dependency-inventory/
│   ├── migration-workbench/
│   ├── verification/
│   └── capsule/
├── pages/
├── hooks/
└── styles/
```

Avoid a giant component that handles repository submission, polling, risk rendering, model output and downloads in one file. Keep fetch calls in `src/api`, types in `src/types`, and feature UI isolated enough for the team to work in parallel.

## 7. Errors and resiliency

- Use one typed API error shape (`code`, `message`, `details`, `request_id`).
- Handle 404 for unknown IDs, 422 validation errors, 409 invalid job state, 503 unavailable service and network failures.
- Poll only active jobs; stop on terminal states. Apply backoff after repeated errors and offer manual retry.
- Avoid stale data: invalidate/refetch analysis/dependency queries after recommendations or verification completes.
- Preserve an existing successful scan when the model service is unavailable; present “scan complete, AI recommendations unavailable” rather than a full-page failure.
- Download endpoints should return a proper file name and content type. Surface an error if the export is rejected by backend schema validation.
- Do not store private repository source or secrets in local browser storage. The MVP can keep the active `analysis_id` in memory or the URL if the backend treats IDs as non-secret, unguessable identifiers.

## 8. Accessibility and responsive behavior

- Every action must be keyboard accessible and visibly focusable.
- Use semantic headings, labels, table headers and button names.
- Don't communicate statuses by color alone; include text/icons.
- Support reduced motion, adequate contrast and readable text at common laptop resolutions.
- On smaller screens, allow tables to scroll horizontally or switch to a well-structured dependency row/detail layout; do not simply shrink text until unreadable.
- Long file paths, package names and log output must wrap or scroll without breaking the page.

## 9. Frontend testing and release checklist

### Unit/component tests

- Status badges correctly render all run/test/recommendation states.
- Dependency detail renders all nine capsule sections, including empty and unverified values.
- Risk and evidence rendering never substitutes fixture content when API data is absent.
- API client handles non-2xx responses, invalid JSON and network failures.
- Export buttons use backend URLs and respect content disposition.
- The verification confirmation flow requires explicit consent.

### Integration/end-to-end tests

- Enter the local LinkWatch path and start a fresh scan.
- Poll until the backend reports a terminal/ready state; confirm progress reflects API state.
- Open a flagged dependency and inspect source evidence and Gemma 4 recommendation.
- Approve a feasible test profile and verify baseline/replacement results are rendered as returned.
- Open the capsule inspector and download/parse both JSON and Markdown exports.
- Exercise no findings, no candidate, missing model, backend offline, test failure, timeout and skipped replacement checks.

### Frontend release gate

- [ ] `npm ci` succeeds from a clean checkout.
- [ ] TypeScript check and production build pass.
- [ ] No API endpoint is duplicated or inconsistent with the backend README.
- [ ] No model or server secrets are bundled into frontend code.
- [ ] All nine capsule sections display.
- [ ] Every status is driven by real API data.
- [ ] The complete LinkWatch user journey works from the UI.
- [ ] Layout is readable and usable at laptop and narrow-window sizes.
- [ ] No mocked findings are shown outside tests.

## 10. References

- [React](https://react.dev/)
- [Vite](https://vite.dev/guide/)
- [TypeScript](https://www.typescriptlang.org/docs/)
- [FastAPI backend README](../backend/README.md)
- [Root implementation README and capsule contract](../../README.md)
- [Organizer target repository: LinkWatch](https://github.com/rishrek/LinkWatch)

**Frontend rule:** the API owns the truth; the UI makes that truth easy to inspect. A beautiful page is not complete until a real LinkWatch scan can be followed through evidence, verification and the exported capsule.
