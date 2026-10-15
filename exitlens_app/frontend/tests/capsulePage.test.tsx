/**
 * ExitLens — Step 5 tests
 * Dependency Exit Capsule: artifact loading, 9 required sections,
 * multiple flagged candidates, export downloads, error/unavailable states.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import '@testing-library/jest-dom';

// ─── Mock API modules ────────────────────────────────────────────────────────

vi.mock('../src/api/analyses', () => ({
  getCapsuleJson: vi.fn(),
  getCapsuleMarkdown: vi.fn(),
  downloadCapsuleFile: vi.fn(),
}));

import * as analysesApi from '../src/api/analyses';
import { ApiClientError } from '../src/api/client';
import { DependencyExitCapsule } from '../src/types/api';

// ─── Mock Context ────────────────────────────────────────────────────────────

const mockContext = {
  health: {
    data: null,
    isLoading: false,
    isBackendAvailable: true,
    isModelAvailable: true,
    error: null,
    lastChecked: null,
    refetch: vi.fn(),
  },
  activeAnalysis: null as null | ReturnType<typeof makeAnalysis>,
  isSubmitting: false,
  isPolling: false,
  submissionError: null,
  recentRuns: [],
  selectedDependencyIds: [] as string[],
  setSelectedDependencyIds: vi.fn(),
  startAnalysis: vi.fn(),
  clearSubmissionError: vi.fn(),
  selectRun: vi.fn(),
  resetActiveAnalysis: vi.fn(),
};

vi.mock('../src/context/useAnalysisContext', () => ({
  useAnalysisContext: () => mockContext,
}));

// ─── Fixtures ────────────────────────────────────────────────────────────────

function makeAnalysis() {
  return {
    analysis_id: 'test-analysis-001',
    status: 'completed',
    stage: 'completed',
    created_at: '2026-10-15T12:00:00Z',
    repository: { kind: 'local_path' as const, value: 'C:/work/LinkWatch' },
    summary: {
      dependencies_discovered: 10,
      dependencies_flagged: 2,
      recommendations_available: 2,
      baseline_checks: 1,
      replacement_checks: 1,
      checks_passed: 1,
      checks_failed: 0,
      checks_skipped_or_unverified: 0,
    },
  };
}

function makeCapsuleFixture(): DependencyExitCapsule {
  return {
    schema_version: '1.0.0',
    capsule_id: 'cap-001',
    analysis_id: 'test-analysis-001',
    generated_at_utc: '2026-10-15T12:05:00Z',
    tool_version: 'exitlens-0.1.0',
    repository: { kind: 'local_path', value: 'C:/work/LinkWatch' },
    runtime_version: 'Python 3.12.2',
    is_complete: true,
    ai_provenance: {
      provider: 'local_ollama',
      model_tag: 'gemma4:latest',
      inference_method: 'local_adapter_bounded',
      prompt_version: 'exitlens-v1',
    },
    flagged_dependencies: [
      {
        dependency_id: 'dep-requests',
        name: 'requests',
        dependency_details: {
          name: 'requests',
          declared_version: '>=2.20.0',
          resolved_version: '2.31.0',
          manifest_path: 'requirements.txt',
          distribution_name: 'requests',
          summary: 'HTTP library for Python',
        },
        risk_indicators: [
          {
            rule_id: 'UNPINNED_OR_WIDE_CONSTRAINT',
            severity: 'high',
            signal: 'Wide version constraint detected',
            explanation: 'Constraint >=2.20.0 allows unverified major version jumps.',
            evidence_ids: ['ev-001'],
          },
        ],
        usage_locations: [
          {
            file_path: 'src/client.py',
            line_start: 14,
            import_name: 'requests.get',
            excerpt: 'response = requests.get(url, timeout=10)',
            is_test_file: false,
          },
        ],
        proposed_replacement: {
          status: 'available',
          candidate_distribution: 'httpx',
          candidate_specifier: '>=0.24.0',
          rationale: 'httpx provides modern async-capable HTTP support with requests-compatible API.',
          provenance: 'AI_RECOMMENDATION',
          limitations: 'Context managers handle timeouts with minor syntax differences.',
        },
        migration_steps: [
          {
            step_number: 1,
            description: 'Replace import requests with import httpx',
            code_example: 'import httpx',
            provenance: 'AI_RECOMMENDATION',
          },
        ],
        suggested_tests: [
          {
            description: 'Run unit test suite against httpx client',
            test_type: 'pytest',
            code_example: 'pytest tests/test_client.py',
            provenance: 'AI_RECOMMENDATION',
          },
        ],
        executed_test_results: [
          {
            profile_id: 'pytest_baseline',
            status: 'PASSED',
            exit_code: 0,
            duration_seconds: 1.25,
            is_baseline: true,
            stdout_excerpt: '2 passed in 1.25s',
          },
          {
            profile_id: 'pytest_replacement',
            status: 'PASSED',
            exit_code: 0,
            duration_seconds: 1.42,
            is_baseline: false,
            stdout_excerpt: '2 passed in 1.42s',
          },
        ],
        compatibility_gaps: [
          {
            description: 'Timeouts must be explicit on Client rather than session defaults',
            severity: 'medium',
          },
        ],
        open_concerns_limitations: [
          {
            description: 'Async client migration recommended in future sprint',
            category: 'architecture',
          },
        ],
      },
      {
        dependency_id: 'dep-urllib3',
        name: 'urllib3',
        dependency_details: {
          name: 'urllib3',
          declared_version: '==1.26.15',
          resolved_version: '1.26.15',
          manifest_path: 'requirements.txt',
        },
        risk_indicators: [],
        usage_locations: [],
        proposed_replacement: null,
        migration_steps: [],
        suggested_tests: [],
        executed_test_results: [],
        compatibility_gaps: [],
        open_concerns_limitations: [],
      },
    ],
  };
}

// ─── Render Helper ───────────────────────────────────────────────────────────

import { CapsulePage } from '../src/pages/CapsulePage';

function renderCapsulePage(initialEntries = ['/capsule']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <CapsulePage />
    </MemoryRouter>
  );
}

// ─── Test Suite ──────────────────────────────────────────────────────────────

describe('CapsulePage — missing active analysis', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = null;
    vi.clearAllMocks();
  });

  it('renders no active analysis empty state with return to workspace button', () => {
    renderCapsulePage();
    expect(screen.getByText('No Active Repository Analysis')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go to Workspace/i })).toBeInTheDocument();
  });
});

describe('CapsulePage — active analysis & full 9-section inspection', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis() as never;
    vi.clearAllMocks();
    vi.mocked(analysesApi.getCapsuleJson).mockResolvedValue(makeCapsuleFixture());
  });

  it('loads capsule and renders artifact metadata and model provenance', async () => {
    renderCapsulePage();
    expect(screen.getByText('Loading Capsule...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Capsule Ready')).toBeInTheDocument();
    });

    // Metadata
    expect(screen.getByText('Schema v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('exitlens-0.1.0')).toBeInTheDocument();
    expect(screen.getByText('gemma4:latest')).toBeInTheDocument();
    expect(screen.getByText('local_ollama')).toBeInTheDocument();
    expect(screen.getByText('Gate Satisfied')).toBeInTheDocument();
  });

  it('renders multiple flagged dependency selector and switches active candidate', async () => {
    renderCapsulePage();
    await waitFor(() => screen.getByText('Capsule Ready'));

    // Both candidates visible in selector
    expect(screen.getByText('Flagged Dependencies in Capsule (2)')).toBeInTheDocument();
    const urllibBtn = screen.getByRole('button', { name: /urllib3/i });
    expect(urllibBtn).toBeInTheDocument();

    // Switch to urllib3
    fireEvent.click(urllibBtn);
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: /urllib3/i })).toBeInTheDocument();
    });
  });

  it('renders all 9 required sections for the active candidate', async () => {
    renderCapsulePage();
    await waitFor(() => screen.getByText('Capsule Ready'));

    // Check all 9 section titles
    expect(screen.getByText('1. Dependency Details')).toBeInTheDocument();
    expect(screen.getByText('2. Risk Indicators')).toBeInTheDocument();
    expect(screen.getByText('3. Usage Locations')).toBeInTheDocument();
    expect(screen.getByText('4. Proposed Replacement')).toBeInTheDocument();
    expect(screen.getByText('5. Migration Steps')).toBeInTheDocument();
    expect(screen.getByText('6. Suggested Tests')).toBeInTheDocument();
    expect(screen.getByText(/7\. Executed Test Results/i)).toBeInTheDocument();
    expect(screen.getByText('8. Compatibility Gaps')).toBeInTheDocument();
    expect(screen.getByText('9. Open Concerns & Limitations')).toBeInTheDocument();

    // Check section content details
    expect(screen.getByText('HTTP library for Python')).toBeInTheDocument();
    expect(screen.getByText('UNPINNED_OR_WIDE_CONSTRAINT')).toBeInTheDocument();
    expect(screen.getByText('src/client.py')).toBeInTheDocument();
    expect(screen.getByText('httpx')).toBeInTheDocument();
    expect(screen.getByText('Replace import requests with import httpx')).toBeInTheDocument();
    expect(screen.getByText('Run unit test suite against httpx client')).toBeInTheDocument();
    expect(screen.getByText('Baseline Execution')).toBeInTheDocument();
    expect(screen.getByText('Replacement Trial')).toBeInTheDocument();
  });

  it('displays explicit empty explanations for empty sections', async () => {
    renderCapsulePage();
    await waitFor(() => screen.getByText('Capsule Ready'));

    // Switch to urllib3 which has empty lists
    fireEvent.click(screen.getByRole('button', { name: /urllib3/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/No active maintenance risk rules triggered for this package/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/No static import usages identified in scanned source files/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/No replacement candidate identified by Gemma 4/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/No verified test runs executed yet for this package/i)
      ).toBeInTheDocument();
    });
  });

  it('triggers Download JSON and calls downloadCapsuleFile with json format', async () => {
    vi.mocked(analysesApi.downloadCapsuleFile).mockResolvedValue(undefined);

    renderCapsulePage();
    await waitFor(() => screen.getByText('Capsule Ready'));

    const jsonBtn = screen.getByRole('button', { name: /Download JSON/i });
    fireEvent.click(jsonBtn);

    await waitFor(() => {
      expect(analysesApi.downloadCapsuleFile).toHaveBeenCalledWith('test-analysis-001', 'json');
      expect(screen.getByText(/Successfully exported exitlens-capsule-test-analysis-001\.json/i)).toBeInTheDocument();
    });
  });

  it('triggers Download Markdown and calls downloadCapsuleFile with md format', async () => {
    vi.mocked(analysesApi.downloadCapsuleFile).mockResolvedValue(undefined);

    renderCapsulePage();
    await waitFor(() => screen.getByText('Capsule Ready'));

    const mdBtn = screen.getByRole('button', { name: /Download Markdown/i });
    fireEvent.click(mdBtn);

    await waitFor(() => {
      expect(analysesApi.downloadCapsuleFile).toHaveBeenCalledWith('test-analysis-001', 'md');
      expect(screen.getByText(/Successfully exported exitlens-capsule-test-analysis-001\.md/i)).toBeInTheDocument();
    });
  });

  it('handles download failure without falsely displaying success', async () => {
    vi.mocked(analysesApi.downloadCapsuleFile).mockRejectedValue(
      new ApiClientError('Artifact not ready on disk', 404, 'CAPSULE_NOT_FOUND')
    );

    renderCapsulePage();
    await waitFor(() => screen.getByText('Capsule Ready'));

    const jsonBtn = screen.getByRole('button', { name: /Download JSON/i });
    fireEvent.click(jsonBtn);

    await waitFor(() => {
      expect(screen.getByText(/CAPSULE_NOT_FOUND: Artifact not ready on disk/i)).toBeInTheDocument();
      expect(screen.queryByText(/Successfully exported/i)).not.toBeInTheDocument();
    });
  });

  it('handles backend capsule endpoint error and allows retry', async () => {
    vi.mocked(analysesApi.getCapsuleJson).mockRejectedValueOnce(
      new ApiClientError('Backend capsule generator offline', 503, 'SERVICE_UNAVAILABLE')
    );

    renderCapsulePage();

    await waitFor(() => {
      expect(screen.getByText(/Capsule Endpoint Unavailable \[SERVICE_UNAVAILABLE\]/i)).toBeInTheDocument();
    });

    // Retry button loads fixture
    vi.mocked(analysesApi.getCapsuleJson).mockResolvedValueOnce(makeCapsuleFixture());
    const retryBtn = screen.getByRole('button', { name: /Retry Request/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText('Capsule Ready')).toBeInTheDocument();
    });
  });
});
