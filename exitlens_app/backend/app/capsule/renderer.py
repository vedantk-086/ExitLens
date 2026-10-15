"""Dependency Exit Capsule Markdown renderer.

Guarantees 1:1 export parity with the canonical JSON representation by consuming
the exact DependencyExitCapsule Pydantic model.
"""

from app.schemas.capsule import DependencyExitCapsule


def render_capsule_markdown(capsule: DependencyExitCapsule) -> str:
    """Render a canonical 9-section Dependency Exit Capsule as GitHub Flavored Markdown."""
    sections = []

    # Title & Header
    sections.append(f"# Dependency Exit Capsule — Run `{capsule.analysis_id}`\n")
    sections.append(
        f"> **Generated at:** {capsule.generated_at_utc}  \n"
        f"> **Capsule ID:** `{capsule.capsule_id}`  \n"
        f"> **Tool:** {capsule.tool.name} v{capsule.tool.version}  \n"
        f"> **Repository:** `{capsule.repository.source}` (Revision: `{capsule.repository.revision or 'N/A'}`)  \n"
        f"> **Runtime:** Python {capsule.repository.python_version}  \n"
        f"> **AI Model Provenance:** {capsule.ai_provenance.model_family} `{capsule.ai_provenance.model_id}` via {capsule.ai_provenance.inference_method} (Prompt: `{capsule.ai_provenance.prompt_version}`)\n"
    )

    # Summary Table
    s = capsule.summary
    sections.append("## Executive Summary\n")
    sections.append(
        "| Metric | Count |\n"
        "|---|---|\n"
        f"| Dependencies Discovered | {s.dependencies_discovered} |\n"
        f"| Dependencies Flagged for Review | {s.dependencies_flagged} |\n"
        f"| Migration Recommendations Available | {s.recommendations_available} |\n"
        f"| Baseline Verification Checks Executed | {s.baseline_checks} |\n"
        f"| Replacement Trial Checks Executed | {s.replacement_checks} |\n"
        f"| Checks Passed | {s.checks_passed} |\n"
        f"| Checks Failed | {s.checks_failed} |\n"
        f"| Checks Skipped / Unverified | {s.checks_skipped_or_unverified} |\n"
    )

    # Flagged Dependencies Breakdown
    sections.append(f"## Flagged Dependencies ({len(capsule.dependencies)})\n")

    if not capsule.dependencies:
        sections.append("*No dependencies were flagged for migration risk during this scan.*\n")

    for idx, dep in enumerate(capsule.dependencies, 1):
        details = dep.dependency_details
        rep = dep.proposed_replacement

        sections.append(f"### {idx}. `{details.distribution_name}` ({details.declared_specifier})\n")

        # Section 1: Dependency Details
        sections.append(
            "#### 1. Dependency Details\n"
            f"- **Distribution Name:** `{details.distribution_name}`\n"
            f"- **Declared Specifier:** `{details.declared_specifier}`\n"
            f"- **Resolved Version:** `{details.resolved_version or 'Unresolved / Drift'}`\n"
            f"- **Manifest Location:** [`{details.manifest_path}`]({details.manifest_path})\n"
            f"- **Package Manager:** {details.package_manager}\n"
            f"- **Classification:** {details.dependency_type}\n"
            f"- **Runtime Markers:** `{details.runtime_markers or 'None'}`\n"
            f"- **Metadata Availability:** {details.metadata_availability}\n"
        )

        # Section 2: Risk Indicators
        sections.append("#### 2. Risk Indicators\n")
        if dep.risk_indicators:
            sections.append("| Rule ID | Severity | Signal Source | Explanation | Evidence Refs |\n|---|---|---|---|---|")
            for risk in dep.risk_indicators:
                ev_str = ", ".join(f"`{ref}`" for ref in risk.evidence_refs) if risk.evidence_refs else "N/A"
                sections.append(
                    f"| `{risk.rule_id}` | **{risk.severity.value}** | {risk.signal_source} | {risk.explanation} | {ev_str} |"
                )
            sections.append("")
        else:
            sections.append("*No active risk indicators flagged.*\n")

        # Section 3: Usage Locations
        sections.append("#### 3. Usage Locations\n")
        if dep.usage_locations:
            sections.append("| Path | Lines | Discovered Import / Symbol | Evidence ID |\n|---|---|---|---|")
            for loc in dep.usage_locations:
                line_str = f"L{loc.line_start}-{loc.line_end}" if loc.line_start else "N/A"
                usage_info = loc.symbol or loc.import_statement or loc.pattern or "Reference detected"
                sections.append(f"| `{loc.path}` | {line_str} | `{usage_info}` | `{loc.evidence_id}` |")
            sections.append("")
        else:
            sections.append("*No static usage located in scanned source files.* *(Note: Dynamic imports or CLI usages may exist.)*\n")

        # Section 4: Proposed Replacement
        sections.append(
            "#### 4. Proposed Replacement\n"
            f"- **Candidate:** `{rep.distribution_name or 'None identified'}` {f'({rep.specifier})' if rep.specifier else ''}\n"
            f"- **Status:** `{rep.status}`\n"
            f"- **Validation Status:** `{rep.candidate_validation_status}`\n"
            f"- **AI Rationale:** {rep.rationale}\n"
        )

        # Section 5: Migration Steps
        sections.append("#### 5. Migration Steps\n")
        if dep.migration_steps:
            for step in dep.migration_steps:
                target = f" (`{step.target_file}`)" if step.target_file else ""
                review_tag = " *(Human Review Required)*" if step.human_review_required else ""
                sections.append(f"{step.step_number}. **{step.action}**{target}: {step.description}{review_tag}")
            sections.append("")
        else:
            sections.append("*No specific migration steps proposed.*\n")

        # Section 6: Suggested Tests
        sections.append("#### 6. Suggested Tests\n")
        if dep.suggested_tests:
            for test in dep.suggested_tests:
                sections.append(
                    f"- **{test.test_id}** (`{test.suggested_profile}`): {test.objective}\n"
                    f"  - *Relation to Usage:* {test.relation_to_usage}\n"
                    f"  - *Expected Signal:* {test.expected_signal}"
                )
            sections.append("")
        else:
            sections.append("*No custom tests suggested by model.*\n")

        # Section 7: Executed Test Results
        sections.append("#### 7. Executed Test Results\n")
        if dep.executed_test_results:
            sections.append("| Check ID | Run Kind | Profile | Status | Exit Code | Duration | Reason / Signal |\n|---|---|---|---|---|---|---|")
            for res in dep.executed_test_results:
                dur = f"{res.duration_seconds:.2f}s" if res.duration_seconds is not None else "N/A"
                code = str(res.exit_code) if res.exit_code is not None else "N/A"
                reason = res.skip_or_error_reason or "Completed"
                sections.append(
                    f"| `{res.check_id}` | {res.run_kind} | `{res.profile_id}` | **{res.status.value}** | {code} | {dur} | {reason} |"
                )
            sections.append("")
        else:
            sections.append("*Verification tests NOT_RUN or SKIPPED for this dependency.*\n")

        # Section 8: Compatibility Gaps
        sections.append("#### 8. Compatibility Gaps\n")
        if dep.compatibility_gaps:
            for gap in dep.compatibility_gaps:
                verified_tag = "*(Verified via execution)*" if gap.verified else "*(Inferred / Potential)*"
                sections.append(f"- **{gap.title}** {verified_tag}: {gap.description}")
            sections.append("")
        else:
            sections.append("*No compatibility gaps currently identified.* *(Compatibility remains unverified without complete test runs.)*\n")

        # Section 9: Open Concerns & Limitations
        sections.append("#### 9. Open Concerns & Limitations\n")
        if dep.open_concerns_limitations:
            for concern in dep.open_concerns_limitations:
                sections.append(f"- {concern}")
            sections.append("")
        else:
            sections.append("- Verification was bounded by static analysis limits.\n")

        sections.append("---\n")

    # Provenance Legend & Limitations
    sections.append(
        "## Provenance & Verification Legend\n\n"
        "| Tag | Meaning |\n"
        "|---|---|\n"
    )
    for tag, desc in capsule.provenance_legend.items():
        sections.append(f"| `{tag}` | {desc} |")
    sections.append("")

    if capsule.known_limitations:
        sections.append("## Known Limitations\n")
        for lim in capsule.known_limitations:
            sections.append(f"- {lim}")
        sections.append("")

    return "\n".join(sections)
