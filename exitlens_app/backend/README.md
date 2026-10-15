# ExitLens Backend — FastAPI, Repository Analysis, Gemma 4 and Verification

This README defines the backend contract for ExitLens. The backend is the single source of truth for repository findings, run state, recommendations, verification outcomes and Dependency Exit Capsule exports. The React frontend must render backend records rather than derive or invent dependency findings itself.

> **Implementation status:** This is the backend implementation specification. Endpoints and behaviors described here are expected behavior; do not report them as implemented until the routes, services and tests exist.

## 1. Responsibilities

The backend must:

1. Validate the repository input and analysis options.
2. create an analysis run and return a stable `analysis_id`.
3. scan supported dependency manifests and project configuration without executing manifest code.
4. map dependencies to Python imports, files, line references and supporting evidence where static analysis permits.
5. apply transparent, versioned maintenance-risk rules.
6. invoke **Gemma 4** through a local inference adapter by default and validate structured output.
7. run only human-approved, allow-listed verification profiles in a disposable worktree/copy when feasible.
8. compare baseline/replacement outcomes and preserve skipped or unresolved checks.
9. build a complete, versioned capsule with all nine required sections for every flagged dependency.
10. persist run records and serve JSON/Markdown exports through the documented REST API.

The backend does not build HTML, access browser state, modify the user's original repository, execute arbitrary model-generated commands, perform vulnerability-first scanning, or guarantee that an AI-suggested replacement is compatible.

## 2. Intended module boundaries

```text
exitlens_app/backend/
├── README.md
├── requirements.txt
├── .env.example
├── app/
│   ├── main.py                     # FastAPI application, startup and CORS
│   ├── api/v1/routes/
│   │   ├── health.py
│   │   ├── analyses.py
│   │   ├── dependencies.py
│   │   ├── recommendations.py
│   │   ├── verification.py
│   │   └── capsules.py
│   ├── schemas/                    # Pydantic request/response/capsule models
│   ├── services/                   # job lifecycle and orchestration
│   ├── scanner/                    # manifest parsers, file walker, usages
│   ├── risk/                       # versioned transparent rules
│   ├── ai/                         # provider interface, Ollama adapter, prompts
│   ├── verification/               # profiles, disposable workspace, runner
│   ├── capsule/                    # completeness check, JSON/Markdown renderer
│   ├── storage/                    # filesystem records and artifact access
│   └── core/                       # settings, IDs, logging, path safety
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

Keep imports acyclic. The API routes call service functions; service functions orchestrate scanner/risk/AI/verification/capsule modules. The scanner must not import API route code. The capsule renderer consumes a typed result model rather than reaching into arbitrary runtime objects.

## 3. Runtime and configuration

### Supported Python

Use Python 3.12 or 3.13 for the target repository. The event-provided LinkWatch repository is not compatible with Python 3.14. Use one Python version consistently for the backend run and document the version in analysis metadata.

### `.env.example` contract

Create a non-secret `.env.example` with these names and safe local defaults. Parse settings through one typed settings module; do not read environment variables independently across modules.

```dotenv
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
API_PREFIX=/api/v1
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173

# A comma-separated list of permitted local repository roots. Resolve each path canonically.
ALLOWED_REPOSITORY_ROOTS=../..
ENABLE_PUBLIC_HTTPS_GIT_CLONE=true

# Local Gemma 4 inference. Record the actual tag in the capsule.
GEMMA_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
GEMMA_MODEL=gemma4
GEMMA_TIMEOUT_SECONDS=90
GEMMA_MAX_RETRIES=1
PROMPT_VERSION=exitlens-v1

# Relative paths are resolved from the backend working directory.
EXITLENS_DATA_DIR=../../reports/exitlens
MAX_ANALYSIS_FILES=5000
MAX_SINGLE_FILE_BYTES=500000
MAX_TOTAL_SOURCE_BYTES=20000000
MAX_CAPTURED_OUTPUT_BYTES=16000
DEFAULT_TEST_TIMEOUT_SECONDS=90
MAX_TEST_TIMEOUT_SECONDS=180
ALLOW_TEST_NETWORK=false
LOG_LEVEL=INFO
```

These values are intended defaults, not evidence that the model is installed or that an endpoint is already running. Validate model readiness through the health endpoint and expose a clear warning if unavailable. Never return private configuration values to the frontend.

### Model choice and event policy

Default to local Gemma 4 inference using Ollama. Before the event/demo, verify the exact installed model tag, hardware capacity, inference latency and applicable model terms. References: [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) and [Ollama Gemma 4 library](https://ollama.com/library/gemma4).

The event handbook prohibits paid API usage and cloud services. Therefore, do not call a hosted model endpoint in the default configuration. A hosted adapter may be added only if organizers explicitly confirm that this use is allowed. Record the **actual** model identifier, inference method, prompt version and model terms in the capsule.

### Local setup (PowerShell)

Run from the repository root:

```powershell
cd exitlens_app\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use `py -3.12` if 3.12 is the chosen runtime. Confirm Ollama separately:

```powershell
ollama list
ollama run gemma4
```

If the local tag differs, set `GEMMA_MODEL` to the exact installed tag. The backend must use a real provider adapter; unit tests may use a stub, but stub responses must be marked as test fixtures and never presented as real Gemma output in a live analysis.

## 4. API contract

All endpoints use `/api/v1`. Request and response bodies are JSON except capsule downloads. Use Pydantic models for request validation and response serialization.

| Method | Endpoint | Response / behavior |
|---|---|---|
| `GET` | `/api/v1/health` | `200`: API readiness, Python version, configured model ID, provider availability and storage readiness. Do not leak secrets. |
| `POST` | `/api/v1/analyses` | `202`: create job; response includes `analysis_id`, `status`, `stage`, `created_at`. |
| `GET` | `/api/v1/analyses/{analysis_id}` | `200`: current job state, progress, summary counts, warnings, timestamps and artifact availability. |
| `GET` | `/api/v1/analyses/{analysis_id}/dependencies` | `200`: list all scanned dependencies plus risk and usage summaries. Pagination may be added, but the MVP must not silently omit flagged dependencies. |
| `GET` | `/api/v1/analyses/{analysis_id}/dependencies/{dependency_id}` | `200`: full dependency evidence and capsule section data for one item. |
| `POST` | `/api/v1/analyses/{analysis_id}/recommendations` | `202`: regenerate recommendations for selected dependency IDs from stored evidence; not a new scan. |
| `POST` | `/api/v1/analyses/{analysis_id}/verification` | `202`: queue baseline/replacement checks for selected candidates using allow-listed profiles and explicit approval. |
| `GET` | `/api/v1/analyses/{analysis_id}/capsule?format=json` | `200`: canonical machine-readable capsule, `application/json`. |
| `GET` | `/api/v1/analyses/{analysis_id}/capsule?format=md` | `200`: human-readable capsule, `text/markdown`. |

### Create-analysis request

```json
{
  "repository": {
    "kind": "local_path",
    "value": "C:/work/LinkWatch",
    "git_ref": null
  },
  "options": {
    "exclude_paths": [".git", ".venv", "venv", "node_modules", "reports", "exitlens_app"],
    "include_tests": true,
    "use_git_history": true,
    "generate_recommendations": true
  }
}
```

`kind` is `local_path` or `git_url`. For a Git URL, allow only public HTTPS URLs by default, reject embedded credentials and unsafe protocols, use a disposable clone, disable submodules by default and bound clone size/time. Never run the repository's Git hooks or setup scripts. The example path is illustrative; configure actual allowed roots on the machine. The backend must canonicalize paths and enforce the allow-list before reading files.

### Create-analysis response

```json
{
  "analysis_id": "generated-uuid",
  "status": "queued",
  "stage": "validating_repository",
  "created_at": "UTC ISO-8601 timestamp"
}
```

### Analysis status model

Use these run statuses consistently:

- `queued`
- `validating_repository`
- `scanning`
- `mapping_usage`
- `assessing_risk`
- `generating_recommendations`
- `ready_for_verification`
- `verifying`
- `completed`
- `completed_with_warnings`
- `failed`

Progress must reflect work the backend has actually reached. Do not animate fake progress. If Gemma fails, static scanning may still finish and the run should become `completed_with_warnings` with recommendation status unavailable. If there are no flagged candidates, return the real empty state and scanning-coverage notes; do not generate a fictitious candidate.

### Recommendations request

```json
{
  "dependency_ids": ["dependency-id-1", "dependency-id-2"],
  "force_regenerate": false
}
```

The initial pipeline should request recommendations for **all flagged dependencies** when `generate_recommendations=true`. The endpoint above permits a user to retry or regenerate selected recommendations after a provider error. Request size and selected IDs must be validated against the saved scan result.

### Verification request

```json
{
  "dependency_ids": ["dependency-id-1"],
  "baseline_profile_id": "python-pytest-or-unittest-detected",
  "replacement_profile_id": "same-profile-in-disposable-copy",
  "confirm_repository_code_execution": true,
  "allow_network": false,
  "timeout_seconds": 90
}
```

Profile IDs in the example are descriptive; the actual server returns profile IDs it detected/allow-listed. The backend must reject unknown profiles and timeouts above the configured maximum. Do **not** accept `shell_command` supplied by the model or browser. Build argument arrays from trusted profiles. A model-generated patch may be tried only after review, patch-path validation and explicit approval; it must be applied only in a disposable copy.

### Standard error response

```json
{
  "error": {
    "code": "MODEL_UNAVAILABLE",
    "message": "Gemma 4 is not reachable from the configured local provider.",
    "details": {"stage": "generating_recommendations"},
    "request_id": "generated-id"
  }
}
```

Use HTTP 404 for unknown run/dependency IDs, 422 for invalid input, 409 for incompatible run state, 503 for unavailable required service operations, and 500 only for unexpected errors. Do not send stack traces or secrets to the UI; log a request ID instead.

## 5. Scanner and evidence model

### Supported files

Implement non-executing parsing for `requirements.txt` variants, static `[project].dependencies` and supported Poetry/uv sections in `pyproject.toml`, `poetry.lock`, `uv.lock`, `Pipfile`/`Pipfile.lock`, and static dependency metadata in `setup.cfg`. `setup.py` must not be imported/executed; only limited AST/static inspection is allowed. Unsupported includes, dynamic dependency declarations and unknown formats generate a coverage warning.

Walk Python source/test files with bounded file count and file-size limits. Exclude `.git`, virtual environments, `node_modules`, generated reports, caches and the ExitLens app directory when the target root is the submission fork. Keep exclusions configurable so a different repository can be analyzed without modifying source code. Do not follow symlinks outside the approved repository root.

### Evidence record contract

Give each piece of observed evidence a stable per-run ID and type, for example:

```json
{
  "evidence_id": "ev-000123",
  "kind": "manifest_declaration",
  "provenance": "OBSERVED",
  "path": "requirements.txt",
  "line_start": 12,
  "line_end": 12,
  "excerpt": "bounded sanitized excerpt",
  "sha256": "hash-of-source-file-or-evidence",
  "observed_at_utc": "timestamp"
}
```

This is a schema example; values must be generated at runtime. Keep paths repository-relative. Store small sanitized excerpts, not full sensitive files. Every rule/AI claim should point to evidence IDs when applicable. Validate model-provided evidence IDs against the saved evidence package and discard or flag invented references.

### Initial transparent risk rules

Use stable IDs and tests for rules such as:

- `UNPINNED_OR_WIDE_CONSTRAINT`
- `MANIFEST_LOCK_DRIFT`
- `CONFLICTING_DECLARATIONS`
- `LOCKFILE_MISSING_WHERE_EXPECTED`
- `DECLARED_NO_STATIC_USAGE_FOUND` (review-only; not proof of unused code)
- `IMPORT_NOT_MAPPED_TO_DISTRIBUTION`
- `RUNTIME_CONSTRAINT_MISMATCH`
- `DEPRECATED_OR_STALE_METADATA` (only if a trusted/approved metadata source actually supplies the fact)

Each rule includes severity, signal, explanation, evidence IDs and limitations. Do not infer unmaintained status from a pinned/old version alone. Unknown metadata is `not_assessed`, not a negative finding. Vulnerability scanning is not part of the MVP scoring scope.

## 6. Gemma 4 adapter and prompt contract

Implement a provider interface, e.g. `generate_migration_plan(evidence_bundle, dependency_record) -> MigrationRecommendation`. The default adapter talks to the local Ollama endpoint using the configured model tag. Keep provider code separate from business logic so unit tests can inject a deterministic stub.

The model receives:

- The dependency declaration and available resolved metadata.
- Its risk indicators and linked evidence IDs.
- Relevant source/import excerpts and test/config clues only.
- The supported runtime and repository test-profile information.
- The required output schema and instructions to report uncertainty.

The model must return structured fields for candidate status, replacement distribution/specifier if known, rationale, source/usage-aware migration steps, API differences, suggested tests, compatibility concerns and optional patch proposal. Parse into Pydantic models; reject malformed types, unsafe patch paths, unknown evidence IDs and unsupported status values. One schema-repair retry is allowed. Never let the AI choose an arbitrary command for execution.

**Meaningful-AI proof:** save provider/model identity, exact configured tag, prompt version, timestamp, validated recommendation, and evidence references. A fallback/stub used in automated tests must be tagged `test_fixture` and cannot be represented as real Gemma in the UI or submitted evidence.

## 7. Verification service

### Baseline versus replacement

- **Baseline:** run a detected or user-approved test profile against the original dependency state in an isolated copy of the target.
- **Replacement:** only attempt if a candidate has enough information and there is a validated, reviewed migration patch/change set that can be applied to another disposable copy. Update or install the proposed dependency only under the approved environment policy.
- **Comparison:** run comparable profiles where feasible, then compare status, exit code and relevant output. Differences are signals, not an automatic proof of cause.

If the baseline is already failing, preserve its failure and compare carefully; do not claim the replacement introduced it. If the replacement package is not installed/cached and network is disabled, record `SKIPPED` and the exact reason. Do not say the replacement was tested merely because the model proposed tests.

### Safety controls

- Require explicit user confirmation before running repository test code.
- Use disposable copies; never run replacement experiments on the original working tree.
- Allow only server-defined test profiles and argv arrays.
- Keep network off by default and do not auto-install packages from the internet.
- Apply maximum timeout, file/output limits, a restricted environment variable allow-list and no inherited secrets.
- Validate every patch path after normalization; reject path traversal, absolute paths and symlink escapes.
- Bound captured output (default 16 KB per stream) and redact obvious tokens.
- State clearly that a local subprocess and temporary directory are **not** a complete sandbox. For truly untrusted code, use an OS/container isolation layer before execution.

## 8. Dependency Exit Capsule service

Use a single canonical Pydantic schema to render JSON and Markdown. Do not create separate logic that can cause the two exports to drift.

For **every flagged dependency**, include all nine sections:

1. `dependency_details`
2. `risk_indicators`
3. `usage_locations`
4. `proposed_replacement`
5. `migration_steps`
6. `suggested_tests`
7. `executed_test_results`
8. `compatibility_gaps`
9. `open_concerns_limitations`

When a field has no supported content, retain the field with an empty list/null plus an explicit status/reason. Example: a dependency with no viable candidate still has `proposed_replacement.status="no_candidate_identified"` and an explanation. A baseline never attempted has an explicit `NOT_RUN` result (or a documented per-section status if no test profile exists).

Before export, validate:

- Each flagged dependency ID is present exactly once.
- Each of the nine sections is present for every flagged dependency.
- Each evidence ID exists in the run's evidence index.
- Every `EXECUTION_RESULT` has recorded status and a command/profile identifier.
- AI suggestions are labelled `AI_RECOMMENDATION`, not `OBSERVED` or `EXECUTION_RESULT`.
- Markdown and JSON are rendered from the same canonical object.
- Repository source/revision, model provenance, scan scope and generation time are recorded.

### Extra USP features (prioritized)

**P0 — implement if at all possible:**

- **Evidence provenance ledger:** each item is tagged Observed, Inferred, AI Recommendation or Execution Result and links back to paths/line ranges/run IDs.
- **Capsule completeness gate:** fail export validation when a required section is missing; unavailable evidence gets a reason, not an invented result.
- **All-candidate coverage:** ensure every rule-flagged dependency gets a recommendation attempt and capsule record, including error/no-candidate outcomes.

**P1 — add after the core workflow:**

- **Counterfactual Migration Trial:** human-review a proposed patch, apply it only to a disposable copy, and compare baseline vs replacement checks.
- **Reproducibility fingerprint:** record Git commit when available, hashes of parsed manifests, runtime details, rule-set version, prompt version and command profile IDs.
- **Coverage/uncertainty summary:** report what fraction of manifests were parsed, dependencies mapped and checks actually run; this is coverage, not a quality score.

## 9. Persistence, retention and logging

Use filesystem-backed run storage for the MVP. Suggested layout:

```text
reports/exitlens/runs/<analysis_id>/
├── analysis.json
├── evidence.json
├── capsule.json
├── capsule.md
└── verification/
    └── <verification_id>.json
```

Write JSON atomically (temporary file then rename), validate `analysis_id` as a generated UUID, and prevent path traversal. Do not commit this directory. Persist stage changes and warnings so an API restart does not turn an incomplete run into a false success. If a run cannot be resumed after restart, clearly mark it failed/interrupted.

Logs should use request/analysis IDs, avoid full source code, avoid all environment dumps, and redact tokens/secrets. The capsule may be public once exported; sanitize file excerpts and do not include secrets, private URLs with credentials or full environment values.

## 10. Tests and definition of done

### Unit tests

- Manifest parse fixtures and unsupported/dynamic construct warnings.
- Constraint/lock mismatch and conflicting-declaration rules.
- Import-to-distribution mapping uncertainties.
- Stable relative file/line locations and exclusion behavior.
- Path allow-list, URL protocol/credential validation, and traversal defenses.
- Gemma response JSON parsing, malformed output, unknown evidence IDs, timeout and unavailable provider.
- All nine capsule fields required on each flagged dependency.
- Export parity: JSON round-trip and Markdown representation correspond to the same canonical schema.
- Runner timeout, nonzero exit, truncated output, `SKIPPED` and `NOT_RUN` statuses.

### Integration tests

- Run a fresh scan against LinkWatch.
- Run with Gemma enabled and record the actual model identity.
- Simulate model unavailability and confirm scanner facts are retained with a warning.
- Confirm every flagged dependency receives a record and recommendation attempt/status.
- Execute at least one safe baseline check if feasible.
- Exercise replacement verification only when a reviewed patch and environment are available; otherwise assert the skipped reason is serialized.
- Download both capsule formats and verify required sections.

### Backend release gate

Do not call the backend done until health, scan creation, status polling, dependency retrieval, recommendations, verification, and both capsule downloads work end to end. “Endpoint exists” is not equivalent to “workflow works.”

## 11. References

- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Ollama Gemma 4 library](https://ollama.com/library/gemma4)
- [Organizer target repository](https://github.com/rishrek/LinkWatch)
- [Renovate](https://docs.renovatebot.com/)
- [Dependabot](https://docs.github.com/en/code-security/dependabot)

The backend must stay local-first, evidence-driven and compatible with the common API/capsule contract described in the root `README.md`.
