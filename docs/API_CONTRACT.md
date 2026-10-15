# ExitLens API Contract (Implementation Target)

**Status:** agreed implementation contract; it is not a claim that endpoints already exist. API types/OpenAPI must be generated from the implemented FastAPI/Pydantic models. If an adjustment is necessary, update this document and both layer READMEs together before coding against a divergent contract.

## Base and error format

- Base URL: `http://127.0.0.1:8000/api/v1`
- OpenAPI UI after implementation: `http://127.0.0.1:8000/docs`
- Keep API bound to loopback for the local demo unless authenticated remote access is implemented.
- Standard error response:

```json
{
  "error": {
    "code": "MODEL_UNAVAILABLE",
    "message": "The configured local Gemma provider is unavailable.",
    "details": {"stage": "generating_recommendations"},
    "request_id": "generated-id"
  }
}
```

Expected HTTP semantics: `404` unknown run/dependency, `422` invalid request, `409` invalid run-state transition, `503` unavailable required operation, `500` unexpected internal error. Do not expose stack traces, source dumps, secrets, or provider credentials.

## Endpoints

| Method | Path | Successful behavior |
|---|---|---|
| GET | `/health` | API/storage readiness, Python version, model identifier/provider readiness; no secrets |
| POST | `/analyses` | `202 Accepted`; create run and return `analysis_id`, `status`, `stage`, `created_at` |
| GET | `/analyses/{analysis_id}` | Actual run state, current stage, summary counts, warnings, timestamps, artifact availability |
| GET | `/analyses/{analysis_id}/dependencies` | All discovered dependency records, evidence/risk/usage summaries; flagged records cannot be silently omitted |
| GET | `/analyses/{analysis_id}/dependencies/{dependency_id}` | Full detail and capsule sections for one dependency |
| POST | `/analyses/{analysis_id}/recommendations` | Queue/retry recommendations for selected dependency IDs using saved scan evidence; not a rescan |
| POST | `/analyses/{analysis_id}/verification` | Queue explicitly approved allow-listed verification profiles |
| GET | `/analyses/{analysis_id}/capsule?format=json` | Canonical JSON capsule (`application/json`) |
| GET | `/analyses/{analysis_id}/capsule?format=md` | Markdown capsule (`text/markdown`) |

All routes use the `/api/v1` prefix.

## Create-analysis request

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

`repository.kind` is `local_path` or `git_url`. The path above is an example only: resolve it and enforce configured allowed roots. For remote input, allow public HTTPS by default, reject embedded credentials/unsafe protocols, limit clone time/size, use a disposable clone and disable submodules by default. Never execute repository setup scripts, Git hooks, or `setup.py` during discovery.

Successful response shape:

```json
{
  "analysis_id": "generated-uuid",
  "status": "queued",
  "stage": "validating_repository",
  "created_at": "UTC ISO-8601 timestamp"
}
```

## Status vocabulary

Run states (exact values):

`queued`, `validating_repository`, `scanning`, `mapping_usage`, `assessing_risk`, `generating_recommendations`, `ready_for_verification`, `verifying`, `completed`, `completed_with_warnings`, `failed`.

Verification statuses (exact values): `PASSED`, `FAILED`, `ERROR`, `TIMED_OUT`, `SKIPPED`, `NOT_RUN`.

Candidate validation may use `NOT_VERIFIED`; this is not a test status and must never be displayed as a verified pass.

Evidence provenance: `OBSERVED`, `INFERRED`, `AI_RECOMMENDATION`, `EXECUTION_RESULT`, `NOT_VERIFIED`.

## Recommendation request

```json
{
  "dependency_ids": ["dependency-id-1"],
  "force_regenerate": false
}
```

The initial scan should attempt recommendations for every dependency flagged by the deterministic risk engine when `generate_recommendations=true`. Validate selected IDs against the saved analysis. When Gemma is unavailable, preserve scan data and return an explicit unavailable outcome; never fall back silently to static/canned recommendations.

## Verification request

```json
{
  "dependency_ids": ["dependency-id-1"],
  "baseline_profile_id": "server-detected-profile-id",
  "replacement_profile_id": "server-detected-profile-id",
  "confirm_repository_code_execution": true,
  "allow_network": false,
  "timeout_seconds": 90
}
```

Profile IDs must be discovered or explicitly allow-listed by the server. Do not accept arbitrary shell command text from the UI or model. Require explicit confirmation, use a disposable copy/worktree, turn network access off by default, bound time/output, avoid inherited secrets and document that a subprocess plus temporary directory is not a complete sandbox. Never edit the user's original checkout.

## Dependency Exit Capsule

Each analysis capsule contains one record for every dependency flagged by the risk engine. Every flagged dependency record must include all nine sections, even when their content is empty or unavailable (with an explicit reason/status):

1. `dependency_details`
2. `risk_indicators`
3. `usage_locations`
4. `proposed_replacement`
5. `migration_steps`
6. `suggested_tests`
7. `executed_test_results`
8. `compatibility_gaps`
9. `open_concerns_limitations`

The top-level capsule should record schema version, capsule/analysis IDs, UTC generation timestamp, tool version, actual repository source/revision, runtime version or unknown, analysis scope/exclusions, summary counts, evidence, AI provenance (actual model tag/provider/inference method/prompt version or unavailable), provenance legend and known limitations.

Completeness gate:

- Each flagged dependency appears exactly once.
- All nine sections exist per flagged dependency.
- Every evidence reference resolves to the run's evidence index.
- Every execution result includes a real result status and profile/command identifier; no exit code is invented for commands that did not run.
- AI output is `AI_RECOMMENDATION`, never `OBSERVED` or `EXECUTION_RESULT`.
- Both exports are rendered from the same canonical typed object and convey equivalent information.
- Unsupported parsing, model unavailability, skipped checks, unknown metadata and remaining uncertainties are disclosed.

## Frontend data rule

The frontend renders backend response values and status only. It may filter/sort retrieved inventory locally, but it must not create findings, progress, metrics, recommendations, execution results or an alternative capsule. TypeScript API types must be generated from the actual FastAPI OpenAPI document once implemented; do not commit a fabricated OpenAPI snapshot.
