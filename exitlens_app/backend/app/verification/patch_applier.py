"""Safe patch proposal parsing, validation, and application.

Ensures:
- Rejects absolute paths, directory traversal (../), and symlink escapes.
- Applies modifications only within the designated disposable workspace.
- Implements self-contained unified diff application without requiring system git/patch.
"""

from pathlib import Path
import re
from typing import List, Optional, Tuple

from app.ai.validator import validate_patch_security
from app.core.errors import ExitLensError
from app.core.logging import get_logger
from app.core.paths import is_safe_subpath

logger = get_logger("exitlens.verification.patch_applier")


class PatchApplicationError(ExitLensError):
    """Raised when patch proposal validation or application fails."""

    def __init__(self, message: str, code: str = "PATCH_APPLICATION_FAILED") -> None:
        super().__init__(message=message, code=code, status_code=400)


def extract_target_files_from_diff(diff_content: str) -> List[Tuple[str, str]]:
    """Extract (source_file, target_file) path pairs from unified diff headers."""
    pairs: List[Tuple[str, str]] = []
    lines = diff_content.splitlines()
    
    current_src: Optional[str] = None
    for line in lines:
        if line.startswith("--- "):
            raw = line[4:].strip().split("\t")[0].strip()
            # Strip a/ or /dev/null
            if raw.startswith("a/"):
                raw = raw[2:]
            current_src = raw
        elif line.startswith("+++ "):
            raw = line[4:].strip().split("\t")[0].strip()
            if raw.startswith("b/"):
                raw = raw[2:]
            if current_src is not None:
                pairs.append((current_src, raw))
                current_src = None
    return pairs


def clean_diff_path(path_str: str) -> str:
    """Normalize and clean diff path string."""
    clean = path_str.strip().split("\t")[0].strip()
    # Strip git diff prefixes
    if clean.startswith("a/") or clean.startswith("b/"):
        clean = clean[2:]
    return clean.replace("\\", "/")


def apply_unified_diff_to_text(original_text: str, hunks_lines: List[str]) -> str:
    """Apply a list of hunk lines to the original file content."""
    original_lines = original_text.splitlines(keepends=True)
    # If file was empty, lines list is empty
    if not original_lines and original_text:
        original_lines = [original_text]

    result_lines: List[str] = []
    orig_idx = 0

    i = 0
    while i < len(hunks_lines):
        line = hunks_lines[i]
        if line.startswith("@@"):
            # Parse hunk header: @@ -old_start,old_len +new_start,new_len @@
            match = re.match(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@", line)
            if not match:
                i += 1
                continue

            old_start = int(match.group(1))
            # 1-indexed to 0-indexed
            target_start = max(0, old_start - 1)

            # Copy unchanged lines leading up to this hunk
            while orig_idx < target_start and orig_idx < len(original_lines):
                result_lines.append(original_lines[orig_idx])
                orig_idx += 1

            i += 1
            # Process hunk body
            while i < len(hunks_lines) and not hunks_lines[i].startswith("@@"):
                h_line = hunks_lines[i]
                if h_line.startswith(" "):
                    # Context line
                    result_lines.append(h_line[1:] + "\n")
                    orig_idx += 1
                elif h_line.startswith("-"):
                    # Deletion line: advance original index
                    orig_idx += 1
                elif h_line.startswith("+"):
                    # Addition line: add to result
                    result_lines.append(h_line[1:] + "\n")
                elif h_line == "":
                    # Empty context line
                    result_lines.append("\n")
                    orig_idx += 1
                i += 1
        else:
            i += 1

    # Copy remaining unchanged lines after all hunks
    while orig_idx < len(original_lines):
        result_lines.append(original_lines[orig_idx])
        orig_idx += 1

    return "".join(result_lines)


def apply_patch_to_workspace(
    workspace_path: Path,
    patch_content: str,
    patch_id: Optional[str] = None,
) -> None:
    """Validate patch security and apply changes strictly within workspace_path.
    
    Raises:
        PatchApplicationError: If patch is unsafe, malformed, or fails to apply.
    """
    if not patch_content or not patch_content.strip():
        raise PatchApplicationError("Patch content is empty.")

    # 1. Strict security check
    is_safe, sec_err = validate_patch_security(patch_content)
    if not is_safe:
        raise PatchApplicationError(f"Patch security validation failed: {sec_err}")

    # 2. Split diff into per-file patches
    diff_sections = re.split(r"(?=^diff --git|^--- )", patch_content, flags=re.MULTILINE)
    
    for section in diff_sections:
        if not section.strip():
            continue

        pairs = extract_target_files_from_diff(section)
        if not pairs:
            continue

        src_path, dst_path = pairs[0]
        target_rel = dst_path if dst_path != "/dev/null" else src_path
        target_rel = clean_diff_path(target_rel)

        if not target_rel or target_rel == "/dev/null":
            continue

        # Canonicalize target file within disposable workspace
        target_file = (workspace_path / target_rel).resolve()

        # Enforce that target_file is strictly within workspace_path
        if not is_safe_subpath(workspace_path, target_file):
            raise PatchApplicationError(
                f"Patch target path '{target_rel}' resolves outside disposable workspace: {target_file}"
            )

        # Check for symlink escape
        if target_file.is_symlink():
            link_target = target_file.resolve()
            if not is_safe_subpath(workspace_path, link_target):
                raise PatchApplicationError(f"Patch target '{target_rel}' is a symlink pointing outside workspace.")

        # Read existing content if file exists
        original_text = ""
        if target_file.is_file():
            try:
                original_text = target_file.read_text(encoding="utf-8")
            except Exception as exc:
                raise PatchApplicationError(f"Failed to read target file '{target_rel}': {exc}")

        # Extract hunk lines
        lines = section.splitlines()
        hunk_start = -1
        for idx, line in enumerate(lines):
            if line.startswith("@@"):
                hunk_start = idx
                break

        if hunk_start == -1:
            continue

        hunk_lines = lines[hunk_start:]
        new_text = apply_unified_diff_to_text(original_text, hunk_lines)

        # Write updated content
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(new_text, encoding="utf-8")
            logger.debug("Successfully applied patch to %s (patch_id=%s)", target_file, patch_id)
        except Exception as exc:
            raise PatchApplicationError(f"Failed to write patched file '{target_rel}': {exc}")
