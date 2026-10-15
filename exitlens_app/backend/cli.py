#!/usr/bin/env python3
"""ExitLens Terminal CLI.

Runs real dependency migration analysis against any public GitHub repository,
streams live progress from the FastAPI backend, and renders rich terminal output
with Google AI Studio Gemma 4 recommendations and exported PDF/JSON/Markdown capsules.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

BACKEND_BASE_URL = os.environ.get("EXITLENS_BACKEND_URL", "http://127.0.0.1:8000/api/v1")
DEFAULT_TARGET = "https://github.com/rishrek/LinkWatch"


# Terminal Colors & Styling
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner() -> None:
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 80)
    print("                              E X I T L E N S")
    print("           Autonomous Dependency Migration & Risk Intelligence Platform")
    print("           AI Provider: Google AI Studio  |  Model: Gemma 4")
    print("=" * 80)
    print(f"{Colors.RESET}")


def api_request(endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, timeout: int = 120) -> Any:
    """Make HTTP request to ExitLens backend API."""
    url = f"{BACKEND_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            content_type = resp.headers.get_content_type()
            if "application/json" in content_type:
                return json.loads(content.decode("utf-8"))
            elif "application/pdf" in content_type:
                return content  # Return raw bytes for PDF
            return content.decode("utf-8")
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8")
        try:
            parsed = json.loads(err_msg)
            msg = parsed.get("error", {}).get("message") or parsed.get("message") or err_msg
        except Exception:
            msg = err_msg
        raise RuntimeError(f"Backend API error (HTTP {err.code}): {msg}")
    except urllib.error.URLError as err:
        raise ConnectionError(
            f"Cannot connect to ExitLens backend at {BACKEND_BASE_URL}.\n"
            f"Ensure the server is running:\n"
            f"  cd exitlens_app/backend\n"
            f"  .\\.venv\\Scripts\\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
        )


def check_backend_health() -> Dict[str, Any]:
    """Verify backend readiness without printing sensitive data."""
    try:
        health = api_request("health", timeout=5)
        return health
    except Exception as exc:
        raise ConnectionError(str(exc))


def validate_github_url(url: str) -> str:
    """Validate that the supplied URL is a safe public HTTPS GitHub repository."""
    url = url.strip().strip("'\"")
    if not url:
        raise ValueError("Repository URL cannot be empty.")

    # Auto-fix accidental duplicate 'https://' prefixes (e.g. 'https://https://github.com/...')
    url = re.sub(r"^(https://)+", "https://", url, flags=re.IGNORECASE)

    # Auto-prepend https:// if user entered github.com/... without scheme
    if url.lower().startswith("github.com/"):
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError(f"Unsafe protocol '{parsed.scheme}'. Only public HTTPS URLs are accepted.")

    if parsed.username or parsed.password:
        raise ValueError("Embedded credentials in Git URLs are strictly prohibited.")

    hostname = (parsed.hostname or "").lower()
    if hostname != "github.com":
        raise ValueError(f"Host '{hostname}' is not allowed. Only 'github.com' is supported.")

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise ValueError(f"Invalid GitHub repository URL '{url}'. Expected format: https://github.com/<owner>/<repo>")

    owner, repo = path_parts[0], path_parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    clean_url = f"https://github.com/{owner}/{repo}"
    return clean_url


def monitor_analysis(analysis_id: str, max_wait_seconds: int = 600) -> Dict[str, Any]:
    """Poll analysis status and display stage progress with graceful interrupt."""
    print(f"\n{Colors.BOLD}Tracking Analysis Run:{Colors.RESET} {Colors.CYAN}{analysis_id}{Colors.RESET}")
    print(f"{Colors.DIM}(Press Ctrl+C to detach anytime; the analysis will continue on the server){Colors.RESET}\n")

    start_time = time.time()
    last_stage = None

    terminal_states = {"completed", "completed_with_warnings", "failed"}

    stage_display_names = {
        "queued": "Queued for processing",
        "validating_repository": "Validating Repository & Disposable Clone",
        "scanning": "Scanning Manifests (non-executing)",
        "mapping_usage": "Static AST Usage Mapping",
        "assessing_risk": "Deterministic Risk Assessment",
        "generating_recommendations": "Generating Google AI Studio Gemma 4 Recommendations",
        "ready_for_verification": "Ready for Verification",
        "completed": "Completed Successfully",
        "completed_with_warnings": "Completed with Warnings",
        "failed": "Analysis Failed",
    }

    try:
        while time.time() - start_time < max_wait_seconds:
            status_resp = api_request(f"analyses/{analysis_id}")
            current_status = status_resp.get("status")
            current_stage = status_resp.get("stage")
            progress = status_resp.get("progress", {})
            percent = progress.get("percent", 0)
            message = progress.get("message", "")
            elapsed = int(time.time() - start_time)

            if current_stage != last_stage:
                if last_stage is not None:
                    print(f"  {Colors.GREEN}[OK]{Colors.RESET} {stage_display_names.get(last_stage, last_stage)}")
                last_stage = current_stage
                print(f"  {Colors.YELLOW}[..]{Colors.RESET} [{elapsed}s] {stage_display_names.get(current_stage, current_stage)} ({percent}%) - {message}")

            if current_status in terminal_states:
                if current_status == "completed":
                    print(f"  {Colors.GREEN}[OK]{Colors.RESET} {stage_display_names.get(current_stage, current_stage)} (100%)")
                elif current_status == "completed_with_warnings":
                    print(f"  {Colors.YELLOW}[OK]{Colors.RESET} {stage_display_names.get(current_stage, current_stage)}")
                else:
                    print(f"  {Colors.RED}[FAIL]{Colors.RESET} {stage_display_names.get(current_stage, current_stage)}")
                return status_resp

            time.sleep(2.5)

        raise TimeoutError(f"Analysis timed out after {max_wait_seconds} seconds.")

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}{Colors.BOLD}[!] Monitoring detached by user.{Colors.RESET}")
        print(f"The analysis run is still actively executing in the backend:")
        print(f"  Analysis ID: {Colors.CYAN}{analysis_id}{Colors.RESET}")
        print(f"\nTo check status and generate the PDF report when ready, run:")
        print(f"  {Colors.BOLD}python cli.py --view {analysis_id}{Colors.RESET}\n")
        sys.exit(0)


def render_report(analysis_id: str, final_status: Dict[str, Any], pdf_output_path: Optional[str] = None) -> None:
    """Print complete rich report of dependencies, risks, AI migration plans, and capsules."""
    capsule = api_request(f"analyses/{analysis_id}/capsule?format=json")
    summary = capsule.get("summary", {})
    repo_scope = capsule.get("repository", {})
    ai_prov = capsule.get("ai_provenance", {})

    target_source = repo_scope.get("source") or "repository"
    repo_name = target_source.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    print(f"\n{Colors.CYAN}{Colors.BOLD}" + "=" * 80)
    print("                             ANALYSIS SUMMARY")
    print("=" * 80 + f"{Colors.RESET}")
    print(f"  {Colors.BOLD}Target Repository:{Colors.RESET}  {target_source}")
    print(f"  {Colors.BOLD}Commit Revision:{Colors.RESET}    {repo_scope.get('revision') or 'HEAD'}")
    print(f"  {Colors.BOLD}Analysis ID:{Colors.RESET}        {analysis_id}")
    print(f"  {Colors.BOLD}Final Status:{Colors.RESET}       {final_status.get('status')}")
    print(f"  {Colors.BOLD}Dependencies:{Colors.RESET}       Discovered: {summary.get('dependencies_discovered')} | Flagged for Migration: {summary.get('dependencies_flagged')}")
    print(f"  {Colors.BOLD}AI Inference:{Colors.RESET}       Provider: {ai_prov.get('provider')} | Model: {ai_prov.get('model_id')}")
    print(f"  {Colors.BOLD}Method:{Colors.RESET}             {ai_prov.get('inference_method')} (Prompt: {ai_prov.get('prompt_version')})")

    warnings = final_status.get("warnings", [])
    if warnings:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}Warnings Encountered ({len(warnings)}):{Colors.RESET}")
        for w in warnings:
            print(f"  - {w}")

    deps = capsule.get("dependencies", [])
    print(f"\n{Colors.CYAN}{Colors.BOLD}" + "=" * 80)
    print(f"                   FLAGGED DEPENDENCIES FOR MIGRATION ({len(deps)})")
    print("=" * 80 + f"{Colors.RESET}")

    for idx, d in enumerate(deps, 1):
        dep_details = d.get("dependency_details", {})
        dep_name = dep_details.get("distribution_name") or "unknown"
        spec = dep_details.get("declared_specifier") or "unpinned"
        resolved = dep_details.get("resolved_version") or "Unresolved / Drift"
        manifest = dep_details.get("manifest_path") or "unknown"
        pkg_manager = dep_details.get("package_manager") or "pip"
        dep_type = dep_details.get("dependency_type") or "direct"
        markers = dep_details.get("runtime_markers") or "None"

        usages = d.get("usage_locations", [])
        risks = d.get("risk_indicators", [])
        prop = d.get("proposed_replacement", {})
        steps = d.get("migration_steps", [])
        tests = d.get("suggested_tests", [])
        exec_tests = d.get("executed_test_results", [])
        gaps = d.get("compatibility_gaps", [])
        concerns = d.get("open_concerns_limitations", [])

        print(f"\n{Colors.BOLD}{Colors.CYAN}[{idx}] Package: {dep_name}{Colors.RESET} ({spec})")
        print(f"    {Colors.DIM}" + "-" * 74 + f"{Colors.RESET}")

        # 1. Dependency Details
        print(f"    {Colors.BOLD}1. Dependency Details:{Colors.RESET}")
        print(f"       - Distribution Name: {Colors.CYAN}{dep_name}{Colors.RESET}")
        print(f"       - Declared Specifier: {spec}")
        print(f"       - Resolved / Locked: {resolved}")
        print(f"       - Manifest Location: {manifest}")
        print(f"       - Package Manager: {pkg_manager} | Classification: {dep_type}")
        print(f"       - Runtime Markers: {markers}")

        # 2. Risk Indicators
        print(f"    {Colors.BOLD}2. Risk Indicators ({len(risks)}):{Colors.RESET}")
        if risks:
            for r in risks:
                sev = r.get("severity", "MEDIUM").upper()
                rule = r.get("rule_id", "RISK")
                title = r.get("title", "")
                expl = r.get("explanation", "")
                sev_color = Colors.RED if sev in ("HIGH", "CRITICAL") else (Colors.YELLOW if sev == "MEDIUM" else Colors.BLUE)
                print(f"       - {sev_color}[{sev}]{Colors.RESET} {Colors.BOLD}{rule}:{Colors.RESET} {title}")
                if expl and expl != title:
                    print(f"         {Colors.DIM}Explanation:{Colors.RESET} {expl}")
        else:
            print(f"       - {Colors.DIM}No active risk indicators flagged.{Colors.RESET}")

        # 3. Usage Locations
        print(f"    {Colors.BOLD}3. Usage Locations ({len(usages)} occurrences):{Colors.RESET}")
        if usages:
            for u in usages[:8]:
                path = u.get("path", "")
                l_start = u.get("line_start")
                l_end = u.get("line_end")
                l_str = f"L{l_start}-{l_end}" if l_start else "Line N/A"
                sym = u.get("symbol") or u.get("import_statement") or "Import reference"
                ev_id = u.get("evidence_id", "")
                print(f"       - {Colors.CYAN}{path}{Colors.RESET} ({l_str}): {Colors.BOLD}{sym}{Colors.RESET} [{ev_id}]")
            if len(usages) > 8:
                print(f"       - {Colors.DIM}... and {len(usages) - 8} more usage locations.{Colors.RESET}")
        else:
            print(f"       - {Colors.DIM}No static imports found in source code (may be dynamic or CLI entrypoint).{Colors.RESET}")

        # 4. Proposed Replacement
        status = prop.get("status", "unknown")
        candidate = prop.get("distribution_name")
        cand_spec = prop.get("specifier") or ""
        val_status = prop.get("candidate_validation_status", "NOT_VERIFIED")
        rationale = prop.get("rationale") or "None"

        print(f"    {Colors.BOLD}4. Proposed Replacement:{Colors.RESET}")
        if status == "proposed":
            print(f"       - Candidate: {Colors.GREEN}{Colors.BOLD}{candidate} {cand_spec}{Colors.RESET} (Status: {status}, Validation: {val_status})")
            print(f"       - AI Rationale: {rationale}")
        elif status == "no_candidate_identified":
            print(f"       - Candidate: {Colors.YELLOW}No drop-in candidate identified{Colors.RESET} (Status: {status})")
            print(f"       - Rationale: {rationale}")
        else:
            print(f"       - Candidate: {Colors.RED}{status}{Colors.RESET}")
            print(f"       - Rationale: {rationale}")

        # 5. Migration Steps
        print(f"    {Colors.BOLD}5. Migration Steps ({len(steps)}):{Colors.RESET}")
        if steps:
            for s in steps:
                s_num = s.get("step_number", "")
                action = s.get("action") or "Update"
                desc = s.get("description") or s.get("instruction") or ""
                target = f" [target: {s.get('target_file')}]" if s.get("target_file") else ""
                print(f"       {s_num}. {Colors.CYAN}{action}:{Colors.RESET} {desc}{target}")
        else:
            print(f"       - {Colors.DIM}No specific migration steps proposed.{Colors.RESET}")

        # 6. Suggested Tests
        print(f"    {Colors.BOLD}6. Suggested Tests ({len(tests)}):{Colors.RESET}")
        if tests:
            for t in tests:
                prof = t.get("suggested_profile") or "pytest"
                obj = t.get("objective") or t.get("test_name") or "Verify compatibility"
                expected = t.get("expected_signal") or ""
                print(f"       - {Colors.BOLD}[{prof}]{Colors.RESET} {obj} (Expected: {expected})")
        else:
            print(f"       - {Colors.DIM}No custom tests suggested by model.{Colors.RESET}")

        # 7. Executed Test Results
        print(f"    {Colors.BOLD}7. Executed Test Results:{Colors.RESET}")
        if exec_tests:
            for r in exec_tests:
                res_status = r.get("status", "NOT_RUN")
                p_id = r.get("profile_id", "pytest")
                exit_c = r.get("exit_code", "N/A")
                dur = r.get("duration_seconds", "N/A")
                reason = r.get("skip_or_error_reason") or "Completed"
                print(f"       - [{res_status}] Profile: {p_id} (Exit Code: {exit_c}, Duration: {dur}s) - {reason}")
        else:
            print(f"       - {Colors.DIM}None (Verification tests NOT_RUN / SKIPPED - explicit human approval required before running tests).{Colors.RESET}")

        # 8. Compatibility Gaps
        print(f"    {Colors.BOLD}8. Compatibility Gaps ({len(gaps)}):{Colors.RESET}")
        if gaps:
            for g in gaps:
                verified_str = "Verified" if g.get("verified") else "Inferred"
                print(f"       - [{verified_str}] {Colors.BOLD}{g.get('title')}:{Colors.RESET} {g.get('description')}")
        else:
            print(f"       - {Colors.DIM}None identified via static analysis (behavioral compatibility requires dynamic verification).{Colors.RESET}")

        # 9. Open Concerns & Limitations
        print(f"    {Colors.BOLD}9. Open Concerns & Limitations ({len(concerns)}):{Colors.RESET}")
        if concerns:
            for c in concerns:
                print(f"       - {c}")
        else:
            print(f"       - {Colors.DIM}Verification bounded by non-executing static analysis limits.{Colors.RESET}")

    # Generate and Export PDF Deliverable
    print(f"\n{Colors.CYAN}{Colors.BOLD}" + "=" * 80)
    print("                       DELIVERABLE REPORT & CAPSULES")
    print("=" * 80 + f"{Colors.RESET}")

    # Resolve runs directory
    runs_dir = os.path.abspath(f"../../reports/exitlens/runs/{analysis_id}")
    if not os.path.exists(runs_dir):
        runs_dir = os.path.abspath(f"reports/exitlens/runs/{analysis_id}")

    # Determine local PDF destination
    default_pdf_name = f"exitlens_report_{repo_name}.pdf"
    local_pdf = os.path.abspath(pdf_output_path or default_pdf_name)
    run_pdf = os.path.join(runs_dir, "capsule.pdf")

    # Download PDF deliverable from backend
    try:
        pdf_bytes = api_request(f"analyses/{analysis_id}/capsule?format=pdf", timeout=30)
        if isinstance(pdf_bytes, str):
            pdf_bytes = pdf_bytes.encode("latin-1")

        with open(local_pdf, "wb") as f:
            f.write(pdf_bytes)
        with open(run_pdf, "wb") as f:
            f.write(pdf_bytes)

        pdf_size_kb = len(pdf_bytes) / 1024
        print(f"  {Colors.GREEN}{Colors.BOLD}[OK] PDF Report Generated:{Colors.RESET} {local_pdf} ({pdf_size_kb:.1f} KB)")
        print(f"  {Colors.GREEN}Archived PDF Capsule:{Colors.RESET} {run_pdf}")
    except Exception as pdf_err:
        print(f"  {Colors.YELLOW}[!] PDF Generation Notice:{Colors.RESET} {pdf_err}")

    print(f"  {Colors.GREEN}Canonical JSON Capsule:{Colors.RESET} {os.path.join(runs_dir, 'capsule.json')}")
    print(f"  {Colors.GREEN}Markdown Report Capsule:{Colors.RESET} {os.path.join(runs_dir, 'capsule.md')}")
    print(f"  {Colors.GREEN}Raw Evidence Ledger:{Colors.RESET} {os.path.join(runs_dir, 'evidence.json')}")
    print(f"  {Colors.GREEN}Analysis Lifecycle Run:{Colors.RESET} {os.path.join(runs_dir, 'analysis.json')}")

    # Test Profiles
    try:
        profiles = api_request(f"analyses/{analysis_id}/test-profiles")
        print(f"\n{Colors.CYAN}{Colors.BOLD}" + "=" * 80)
        print("                 DETECTED TEST PROFILES (VERIFICATION NOT RUN)")
        print("=" * 80 + f"{Colors.RESET}")
        for p in profiles:
            print(f"  - Profile: {Colors.BOLD}{p.get('profile_id')}{Colors.RESET} (Framework: {p.get('framework')})")
            print(f"    Command: {' '.join(p.get('argv', []))}")
        print(f"\n  {Colors.GREEN}[SAFETY CONFIRMATION]{Colors.RESET} Scanning was strictly static & non-executing.")
        print("  Repository code, tests, and setup scripts were NEVER executed.")
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run real ExitLens dependency migration analysis against any public GitHub repository.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Public HTTPS GitHub repository URL (e.g. https://github.com/rishrek/LinkWatch)",
    )
    parser.add_argument(
        "--view",
        metavar="ANALYSIS_ID",
        default=None,
        help="View results and generate PDF report for an existing analysis ID",
    )
    parser.add_argument(
        "--pdf-out",
        metavar="PATH",
        default=None,
        help="Custom destination path for the generated PDF report",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Fast mode: Disable cloud AI recommendations (manifest scan & risk assessment only in ~3s)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum polling wait time in seconds (default: 600)",
    )

    args = parser.parse_args()

    print_banner()

    # Mode 1: View Existing Analysis and Generate PDF
    if args.view:
        analysis_id = args.view.strip()
        print(f"{Colors.BOLD}Loading Analysis Run:{Colors.RESET} {Colors.CYAN}{analysis_id}{Colors.RESET}")
        try:
            status = api_request(f"analyses/{analysis_id}")
            render_report(analysis_id, status, pdf_output_path=args.pdf_out)
            return
        except Exception as exc:
            print(f"\n{Colors.RED}Failed to load analysis '{analysis_id}': {exc}{Colors.RESET}")
            sys.exit(1)

    # Step 1: Health Check
    print(f"{Colors.BOLD}1. Checking ExitLens Backend Readiness...{Colors.RESET}")
    try:
        health = check_backend_health()
        print(f"   Status: {Colors.GREEN}{health.get('status').upper()}{Colors.RESET}")
        print(f"   Python: {health.get('python', {}).get('version')} (Compatible: {health.get('python', {}).get('is_compatible')})")
        print(f"   AI Provider: {health.get('ai', {}).get('provider')} ({health.get('ai', {}).get('configured_model')})")
        print(f"   Storage: Ready={health.get('storage', {}).get('ready')}, Writable={health.get('storage', {}).get('writable')}")
    except ConnectionError as err:
        print(f"\n{Colors.RED}{err}{Colors.RESET}")
        sys.exit(1)

    # Step 2: Get Repository URL
    target_url = args.url
    if not target_url:
        print(f"\n{Colors.BOLD}2. Enter GitHub Repository URL{Colors.RESET}")
        prompt = f"   Repository URL [{Colors.CYAN}{DEFAULT_TARGET}{Colors.RESET}]: "
        try:
            user_input = input(prompt).strip()
            target_url = user_input if user_input else DEFAULT_TARGET
        except (KeyboardInterrupt, EOFError):
            print("\nAborted by user.")
            sys.exit(0)

    try:
        clean_url = validate_github_url(target_url)
        print(f"   Validated: {Colors.GREEN}{clean_url}{Colors.RESET}")
    except ValueError as val_err:
        print(f"\n{Colors.RED}Validation Error: {val_err}{Colors.RESET}")
        sys.exit(1)

    # Step 3: Initiate Analysis
    print(f"\n{Colors.BOLD}3. Initiating Analysis Run...{Colors.RESET}")
    payload = {
        "repository": {
            "kind": "git_url",
            "value": clean_url,
            "git_ref": None,
        },
        "options": {
            "exclude_paths": [".git", ".venv", "venv", "node_modules", "reports", "exitlens_app"],
            "include_tests": True,
            "use_git_history": True,
            "generate_recommendations": not args.no_ai,
        },
    }

    try:
        created = api_request("analyses", method="POST", data=payload)
        analysis_id = created["analysis_id"]
        print(f"   Analysis ID: {Colors.CYAN}{analysis_id}{Colors.RESET}")
        print(f"   Status: {created.get('status')} | Stage: {created.get('stage')}")
    except Exception as exc:
        print(f"\n{Colors.RED}Failed to create analysis: {exc}{Colors.RESET}")
        sys.exit(1)

    # Step 4: Monitor Run
    try:
        final_status = monitor_analysis(analysis_id, max_wait_seconds=args.timeout)
    except Exception as exc:
        print(f"\n{Colors.RED}Analysis tracking error: {exc}{Colors.RESET}")
        sys.exit(1)

    # Step 5: Render Full Report and Generate PDF
    render_report(analysis_id, final_status, pdf_output_path=args.pdf_out)


if __name__ == "__main__":
    main()
