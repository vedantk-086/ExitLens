# ExitLens Backend — Developer & Quality Assurance Guide

ExitLens is a local-first, evidence-grounded dependency migration analysis platform. The backend is the single source of truth for repository findings, run state, recommendations, verification outcomes, and Dependency Exit Capsule exports.

---

## 1. Architecture & Design Principles

The backend is built with Python 3.12/3.13, FastAPI, and Pydantic v2. It adheres to strict architectural boundaries:

```text
exitlens_app/backend/
├── requirements.txt            # Locked runtime & testing dependencies
├── .env.example                # Safe environment variable configuration template
├── app/
│   ├── main.py                 # FastAPI application, CORS, lifespan, exception handlers
│   ├── api/v1/routes/          # REST route handlers (HTTP protocol only, no business logic)
│   │   ├── health.py           # GET /api/v1/health
│   │   ├── analyses.py         # POST /api/v1/analyses, GET /api/v1/analyses, GET /api/v1/analyses/{id}
│   │   ├── dependencies.py     # GET /analyses/{id}/dependencies, GET /analyses/{id}/dependencies/{dep_id}
│   │   ├── recommendations.py  # POST /api/v1/analyses/{id}/recommendations
│   │   ├── verification.py     # GET /analyses/{id}/test-profiles, POST /analyses/{id}/verification
│   │   └── capsules.py         # GET /analyses/{id}/capsule?format=json|md
│   ├── schemas/                # Canonical Pydantic schemas (requests, responses, capsule models)
│   ├── services/               # Orchestration and job lifecycle management
│   ├── scanner/                # Non-executing manifest parsers, AST walker, usage mapper
│   ├── risk/                   # Versioned, transparent maintenance-risk rules
│   ├── ai/                     # AI provider interface, Google AI Studio provider, fake test fixture
│   ├── verification/           # Disposable workspace runner with allow-listed test profiles
│   ├── capsule/                # Completeness validator, JSON serializer, and Markdown renderer
│   ├── storage/                # Atomic filesystem storage for run records and artifacts
│   └── core/                   # Typed settings, UUIDs, ISO timestamps, logging, path safety, error types
└── tests/
    ├── conftest.py             # Shared pytest fixtures (temp directories, test settings, ASGI client)
    ├── fixtures/               # Realistic repository fixtures (LinkWatch, multi-manifest, corrupted)
    ├── unit/                   # Comprehensive unit tests (105+ tests covering all modules)
    └── integration/            # End-to-end integration tests (LinkWatch workflow, degraded models)
```

### Core Invariants:
1. **Never Execute Repository Code During Scanning**: Repository manifests and Python sources are parsed strictly using non-executing parsers and Python's native `ast` module. `setup.py` is inspected via AST, never executed or imported.
2. **Deterministic Risk Assessment**: Maintenance risks are inferred using transparent, versioned rules linked to concrete evidence IDs. Version age alone is never equated with abandonment.
3. **Decoupled AI Layer**: Google AI Studio (hosted Gemma models) and local Ollama are supported through an abstract provider interface. Unit and integration tests run offline against deterministic test stubs (`test_fixture`). Real cloud AI output is never faked.
4. **Disposable Workspace Verification**: Repository test code executes only when the user explicitly approves (`confirm_repository_code_execution=True`), using allow-listed server-defined argument arrays inside isolated temporary directories.
5. **Canonical Capsule Parity**: JSON and Markdown deliverables are rendered from the same canonical Pydantic model (`DependencyExitCapsule`), validated by a 9-section completeness gate before persistence.

---

## 2. Python & Virtual Environment Setup

### Supported Python Versions
- **Recommended**: Python 3.12 or Python 3.13.
- **Incompatible**: Python 3.14 (incompatible with dependencies in the organizer-provided LinkWatch repository).

### Step-by-Step Setup (PowerShell / Windows)

From the project root:

```powershell
# 1. Navigate to the backend directory
cd exitlens_app\backend

# 2. Create a virtual environment using Python 3.12 or 3.13
py -3.13 -m venv .venv

# 3. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt

# 6. Initialize local configuration
Copy-Item .env.example .env
```

---

## 3. Environment Configuration (`.env`)

Configure `exitlens_app/backend/.env` according to your deployment mode:

```dotenv
# Application Environment
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
API_PREFIX=/api/v1
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173

# Allowed Repository Roots (comma-separated; resolved canonically)
ALLOWED_REPOSITORY_ROOTS=../..
ENABLE_PUBLIC_HTTPS_GIT_CLONE=true

# AI Provider Selection: 'google_ai_studio', 'ollama', or 'test_fixture'
GEMMA_PROVIDER=google_ai_studio

# Google AI Studio Configuration (Hosted)
# Leave empty for offline test mode; set for live Gemma 4 migration plans
GOOGLE_AI_API_KEY=
GOOGLE_AI_MODEL=gemma-4-26b-a4b-it
GOOGLE_AI_TIMEOUT_SECONDS=90
GOOGLE_AI_MAX_RETRIES=1
PROMPT_VERSION=exitlens-v1

# Optional Local Ollama Settings (Alternative offline inference)
OLLAMA_BASE_URL=http://127.0.0.1:11434
GEMMA_MODEL=gemma4

# Storage & Operational Bounds
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

### AI Provider Setup Options

#### Option A: Google AI Studio (Hosted Gemma 4 Models)
1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Set `GOOGLE_AI_API_KEY=your_key_here` in `.env`.
3. Set `GEMMA_PROVIDER=google_ai_studio` and `GOOGLE_AI_MODEL=gemma-4-26b-a4b-it` (or `gemma-4-31b-it`).
4. *Event Policy Note:* Confirm that hosted AI usage is permitted by the event/hackathon rules before enabling for a live demo. Secrets are never exposed to API responses, logs, or exports.

#### Option B: Local Ollama (Offline Development)
1. Install [Ollama](https://ollama.com/) locally.
2. Pull the model:
   ```powershell
   ollama pull gemma4
   ```
3. Set `GEMMA_PROVIDER=ollama` in `.env`.
4. If Ollama is offline or unreachable, the backend preserves all static scan evidence and records an honest `UNAVAILABLE` recommendation state.

#### Option C: Deterministic Test Stubs (`test_fixture`)
1. Set `GEMMA_PROVIDER=test_fixture` in `.env`.
2. Fully deterministic, offline execution with zero API calls or quota consumption.
3. Provenance is explicitly tagged `provider="test_fixture"` and `inference_method="test_fixture"`.

---

## 4. Running the API

Start the backend with Uvicorn:

```powershell
# From exitlens_app\backend with .venv activated:
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Endpoints Overview
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Specification**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## 5. Running Tests & Static Checks

### Running the Test Suite
The test suite consists of unit tests and end-to-end integration tests using `pytest` and `httpx`:

```powershell
# Run all unit and integration tests:
python -m pytest -v

# Run only unit tests:
python -m pytest tests/unit -v

# Run only LinkWatch integration tests:
python -m pytest tests/integration -v
```

### Static Python Compilation Check
Verify syntax and bytecode compilation across all backend modules:

```powershell
python -m compileall app tests
```

---

## 6. Safety Architecture & Limitations

ExitLens enforces defense-in-depth safety boundaries:

| Safety Domain | Protection Mechanism |
|---|---|
| **Repository Scanning** | Manifests and Python sources are parsed using non-executing AST visitors. `setup.py` code is never executed. Recursive includes (`-r`) have a recursion depth limit (10) preventing infinite include loops. |
| **Path Traversal Defenses** | All input paths are resolved canonically. Paths outside `ALLOWED_REPOSITORY_ROOTS`, null bytes, and traversal sequences (`..`) are rejected with HTTP 422. Symlink escapes outside allowed roots are blocked. |
| **Test Verification Approval** | Test execution requires explicit approval (`confirm_repository_code_execution=True`). Unconfirmed requests return HTTP 422 `CONFIRMATION_REQUIRED`. |
| **Server-Defined Profiles** | Clients cannot specify arbitrary shell commands. Only allow-listed, server-defined profiles (`pytest-default`, `pytest-verbose`, `unittest-discover`) with fixed argument arrays may be executed. |
| **Disposable Workspaces** | Test verification is never run on the user's working tree. The repository is copied to a disposable temporary directory and removed after execution. |
| **Network Isolation** | Subprocess environment enforces `PIP_NO_INDEX=1`, `PIP_OFFLINE=1`, and proxy neutralization (`HTTP_PROXY=http://127.0.0.1:0`). |
| **Output Redaction & Limits** | Captured output is bounded (default 16 KB) and scrubbed for API keys, bearer tokens, passwords, and private URLs before persistence. |

### Critical Sandbox Limitation Disclosure
> [!WARNING]
> A local Python subprocess in a temporary directory provides process isolation, **not** a secure operating system sandbox. It does not prevent low-level OS kernel exploits or malicious code from accessing user files. For untrusted repositories, execute ExitLens inside a container (Docker/Podman) or microVM (gVisor/Firecracker).

---

## 7. Known Unsupported Manifest Patterns

The scanner handles standard Python packaging practices but safely degrades with a logged coverage warning when encountering unsupported constructs:

1. **Dynamic `setup.py` / `setup.cfg`**:
   - Manifests that execute code at parse time (e.g., reading requirements from remote APIs or executing shell commands) are parsed via static AST only. Dynamic expressions produce a coverage warning.
2. **Unsupported pip CLI Options**:
   - Directives such as `-c constraints.txt`, `-i https://custom.pypi.org/simple`, `--extra-index-url`, and `-e .` (editable installs) are recognized and skipped with a warning, rather than crashing the parser.
3. **Circular Recursive Includes**:
   - `requirements.txt` includes referencing each other (e.g., `a.txt -> b.txt -> a.txt`) are bounded by a maximum recursion depth of 10. Once the depth is exceeded, circular includes are aborted with a warning.
4. **Unsupported Lockfile Formats**:
   - Poetry lock (`poetry.lock`), uv lock (`uv.lock`), and Pipenv (`Pipfile.lock`) are parsed statically. Proprietary or binary lockfiles trigger an unsupported format warning.

---

## 8. Release Verification Checklist

Use this checklist to prove that all API routes work together end-to-end:

```text
[x] 1. GET  /api/v1/health
       - Returns HTTP 200 with API status, Python runtime compatibility, storage readiness, and AI provider status.
       - No secrets or API credentials exposed in response.

[x] 2. POST /api/v1/analyses
       - Accepts RepositoryInput and AnalysisOptions.
       - Returns HTTP 202 with analysis_id, status="queued", and stage="validating_repository".

[x] 3. GET  /api/v1/analyses/{analysis_id}
       - Polls status and real progress percentage (0% to 100%).
       - Reaches completed or completed_with_warnings.
       - Artifact availability flags reflect persisted JSON and Markdown deliverables.

[x] 4. GET  /api/v1/analyses/{analysis_id}/dependencies
       - Returns all flagged dependencies with risk indicators, usage locations, and proposed replacements.
       - No duplicate dependency IDs (each flagged dependency appears exactly once).

[x] 5. GET  /api/v1/analyses/{analysis_id}/dependencies/{dependency_id}
       - Returns full 9-section details for a single selected dependency ID.
       - Returns HTTP 404 for unknown dependency IDs.

[x] 6. POST /api/v1/analyses/{analysis_id}/recommendations
       - Regenerates AI migration recommendations for selected dependency IDs from stored evidence.
       - Does not re-scan the repository.
       - Returns HTTP 202 with updated recommendation records.

[x] 7. GET  /api/v1/analyses/{analysis_id}/test-profiles
       - Statically inspects the repository and returns allow-listed test profiles (pytest, unittest).
       - Tags detected profiles with is_detected=True and detection evidence.

[x] 8. POST /api/v1/analyses/{analysis_id}/verification
       - Rejects unconfirmed requests (confirm_repository_code_execution=False) with HTTP 422.
       - Rejects unauthorized profiles with HTTP 422 UNAUTHORIZED_TEST_PROFILE.
       - Executes approved baseline verification in a disposable copy and records results.
       - Safely marks replacement trials SKIPPED when no validated patch is available.

[x] 9. GET  /api/v1/analyses/{analysis_id}/verification/{verification_id}
       - Returns stored verification session record with baseline and replacement results.

[x] 10. GET /api/v1/analyses/{analysis_id}/capsule?format=json
       - Serves canonical Dependency Exit Capsule with application/json header.
       - Passes 9-section capsule completeness validation with 0 errors.

[x] 11. GET /api/v1/analyses/{analysis_id}/capsule?format=md
       - Serves human-readable Markdown deliverable with text/markdown header.
       - Contains Executive Summary, Flagged Dependencies, Provenance Legend, and Known Limitations.

[x] 12. GET /api/v1/analyses/{analysis_id}/capsule?format=invalid
       - Rejects unsupported format with HTTP 422 INVALID_EXPORT_FORMAT.
```
