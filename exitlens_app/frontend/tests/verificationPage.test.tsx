/**
 * ExitLens — Step 4 tests
 * Verification Workbench: safety confirmation, request construction,
 * separate baseline and replacement results, execution states, error handling.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import '@testing-library/jest-dom';

// ─── Mock API modules ────────────────────────────────────────────────────────

vi.mock('../src/api/analyses', () => ({
  getDependencies: vi.fn(),
  getDependencyDetail: vi.fn(),
  postRecommendations: vi.fn(),
  postVerification: vi.fn(),
  createAnalysis: vi.fn(),
  getAnalysis: vi.fn(),
  getTestProfiles: vi.fn().mockResolvedValue([]),
}));

import * as analysesApi from '../src/api/analyses';

// ─── Mock analysis context ───────────────────────────────────────────────────

const mockContext = {
  health: {
    data: null,
    isLoading: false,
    isBackendAvailable: true,
    isModelAvailable: false,
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

function makeAnalysis(status = 'completed') {
  return {
    analysis_id: 'test-analysis-001',
    status,
    stage: status,
    created_at: new Date().toISOString(),
    repository: { kind: 'local_path' as const, value: 'C:/work/LinkWatch' },
    summary: {
      dependencies_discovered: 10,
      dependencies_flagged: 3,
      recommendations_available: 2,
      baseline_checks: 1,
      replacement_checks: 1,
      checks_passed: 1,
      checks_failed: 0,
      checks_skipped_or_unverified: 0,
    },
  };
}

function makeDep(overrides = {}) {
  return {
    dependency_id: 'dep-001',
    name: 'requests',
    declared_version: '>=2.20.0',
    resolved_version: '2.31.0',
    manifest_path: 'requirements.txt',
    highest_severity: 'high',
    risk_rule_ids: ['UNPINNED_OR_WIDE_CONSTRAINT'],
    usage_count: 5,
    recommendation_status: 'available',
    verification_status: null,
    is_flagged: true,
    ...overrides,
  };
}

function makeDetail(overrides = {}) {
  return {
    dependency_id: 'dep-001',
    analysis_id: 'test-analysis-001',
    dependency_details: {
      name: 'requests',
      declared_version: '>=2.20.0',
      resolved_version: '2.31.0',
      manifest_path: 'requirements.txt',
    },
    risk_indicators: [
      {
        rule_id: 'UNPINNED_OR_WIDE_CONSTRAINT',
        severity: 'high',
        signal: 'Wide version constraint detected',
        explanation: 'Unpinned versions may introduce breaking changes.',
      },
    ],
    usage_locations: [],
    proposed_replacement: {
      status: 'available',
      candidate_distribution: 'httpx',
      candidate_specifier: '>=0.24.0',
      rationale: 'httpx is a modern async-capable HTTP client.',
      provenance: 'AI_RECOMMENDATION' as const,
    },
    migration_steps: [],
    suggested_tests: [
      {
        description: 'Run unit test suite with httpx compatibility layer',
        test_type: 'pytest',
        code_example: 'pytest tests/test_client.py',
        provenance: 'AI_RECOMMENDATION' as const,
      },
    ],
    executed_test_results: [],
    compatibility_gaps: [
      {
        description: 'Session parameters difference in timeouts',
        severity: 'medium',
      },
    ],
    open_concerns_limitations: [
      {
        description: 'Async client initialization differs from sync requests.Session',
      },
    ],
    ...overrides,
  };
}

// ─── Render helper ───────────────────────────────────────────────────────────

import { VerificationPage } from '../src/pages/VerificationPage';

function renderVerificationPage(initialEntries = ['/verification']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <VerificationPage />
    </MemoryRouter>
  );
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('VerificationPage — missing active analysis', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = null;
    mockContext.selectedDependencyIds = [];
    vi.clearAllMocks();
  });

  it('renders no active analysis empty state and workspace redirection action', () => {
    renderVerificationPage();
    expect(screen.getByText('No Active Repository Analysis')).toBeInTheDocument();
    expect(screen.getByText('Configure Repository Scan')).toBeInTheDocument();
  });
});

describe('VerificationPage — missing dependency selection', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis() as never;
    mockContext.selectedDependencyIds = [];
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [],
    });
  });

  it('renders no dependencies available state and action to inventory', async () => {
    renderVerificationPage();
    await waitFor(() => {
      expect(
        screen.getByText('No Dependencies Available for Verification')
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Open Dependency Inventory')).toBeInTheDocument();
  });
});

describe('VerificationPage — dependency selected & safety approval flow', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis() as never;
    mockContext.selectedDependencyIds = ['dep-001'];
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [makeDep()],
    });
    vi.mocked(analysesApi.getDependencyDetail).mockResolvedValue(makeDetail() as never);
  });

  it('renders the workbench heading, candidate info, and safety controls', async () => {
    renderVerificationPage();
    expect(screen.getByText('Verification Workbench')).toBeInTheDocument();
    expect(
      screen.getByText(/Safety Boundary & Code Execution Notice/i)
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('httpx')).toBeInTheDocument();
    });
    expect(screen.getByText('Network Disabled (Isolated)')).toBeInTheDocument();
  });

  it('requires human approval before submitting verification', async () => {
    renderVerificationPage();
    await waitFor(() => screen.getByText('httpx'));

    const runButton = screen.getByRole('button', { name: /Review & Run Verification/i });
    fireEvent.click(runButton);

    // Approval modal appears
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Confirm Repository Code Execution/i })).toBeInTheDocument();
    });

    const submitBtn = screen.getByRole('button', { name: /Confirm & Execute Verification/i });
    // Disabled prior to checkbox confirmation
    expect(submitBtn).toBeDisabled();

    // Check confirmation checkbox
    const checkbox = screen.getByLabelText(/I acknowledge and approve executing repository test code/i);
    fireEvent.click(checkbox);
    expect(submitBtn).not.toBeDisabled();
  });

  it('constructs correct verification request payload upon confirmation', async () => {
    vi.mocked(analysesApi.postVerification).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      status: 'queued',
      message: 'Verification trial queued in disposable copy.',
    });

    renderVerificationPage();
    await waitFor(() => screen.getByText('httpx'));

    fireEvent.click(screen.getByRole('button', { name: /Review & Run Verification/i }));
    await waitFor(() => screen.getByRole('heading', { name: /Confirm Repository Code Execution/i }));

    fireEvent.click(screen.getByLabelText(/I acknowledge and approve executing repository test code/i));
    fireEvent.click(screen.getByRole('button', { name: /Confirm & Execute Verification/i }));

    await waitFor(() => {
      expect(analysesApi.postVerification).toHaveBeenCalledWith('test-analysis-001', {
        dependency_ids: ['dep-001'],
        baseline_profile_id: 'server-detected-profile-id',
        replacement_profile_id: 'server-detected-profile-id',
        confirm_repository_code_execution: true,
        allow_network: false,
        timeout_seconds: 90,
      });
    });
  });
});

describe('VerificationPage — accurate separation of baseline and replacement results', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis() as never;
    mockContext.selectedDependencyIds = ['dep-001'];
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [makeDep()],
    });
  });

  it('displays separate baseline passed and replacement skipped without conflation', async () => {
    vi.mocked(analysesApi.getDependencyDetail).mockResolvedValue(
      makeDetail({
        executed_test_results: [
          {
            profile_id: 'pytest-baseline',
            command: 'pytest tests/',
            status: 'PASSED',
            exit_code: 0,
            stdout_excerpt: '12 passed in 0.82s',
            duration_seconds: 0.82,
            is_baseline: true,
          },
          {
            profile_id: 'pytest-replacement',
            command: 'pytest tests/',
            status: 'SKIPPED',
            skip_reason: 'httpx is not installed in isolated cache; network disabled.',
            is_baseline: false,
          },
        ],
      }) as never
    );

    renderVerificationPage();
    await waitFor(() => expect(screen.getByText('12 passed in 0.82s')).toBeInTheDocument());

    // Baseline shows PASSED
    expect(screen.getByText('Baseline Test Suite')).toBeInTheDocument();
    const passedBadges = screen.getAllByText('PASSED');
    expect(passedBadges.length).toBeGreaterThan(0);

    // Replacement shows SKIPPED with exact reason, NOT passed
    expect(screen.getByText('Candidate Replacement Trial')).toBeInTheDocument();
    expect(screen.getByText('SKIPPED')).toBeInTheDocument();
    expect(
      screen.getByText(/httpx is not installed in isolated cache/i)
    ).toBeInTheDocument();
  });

  it('renders FAILED and TIMED_OUT execution statuses accurately', async () => {
    vi.mocked(analysesApi.getDependencyDetail).mockResolvedValue(
      makeDetail({
        executed_test_results: [
          {
            profile_id: 'pytest-baseline',
            command: 'pytest tests/',
            status: 'FAILED',
            exit_code: 1,
            stderr_excerpt: 'AssertionError: test_connection failed',
            duration_seconds: 1.2,
            is_baseline: true,
          },
          {
            profile_id: 'pytest-replacement',
            command: 'pytest tests/',
            status: 'TIMED_OUT',
            duration_seconds: 90.0,
            error_reason: 'Process timed out after 90 seconds.',
            is_baseline: false,
          },
        ],
      }) as never
    );

    renderVerificationPage();
    await waitFor(() => expect(screen.getByText(/AssertionError: test_connection failed/i)).toBeInTheDocument());

    expect(screen.getByText('FAILED')).toBeInTheDocument();
    expect(screen.getByText('TIMED_OUT')).toBeInTheDocument();
    expect(screen.getByText('Process timed out after 90 seconds.')).toBeInTheDocument();
  });
});

describe('VerificationPage — backend error and unavailable states', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis() as never;
    mockContext.selectedDependencyIds = ['dep-001'];
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [makeDep()],
    });
    vi.mocked(analysesApi.getDependencyDetail).mockResolvedValue(makeDetail() as never);
  });

  it('handles backend error gracefully and displays honest error details', async () => {
    const { ApiClientError } = await import('../src/api/client');
    vi.mocked(analysesApi.postVerification).mockRejectedValue(
      new ApiClientError('Verification service unavailable on server.', 503, 'SERVICE_UNAVAILABLE')
    );

    renderVerificationPage();
    await waitFor(() => screen.getByText('httpx'));

    fireEvent.click(screen.getByRole('button', { name: /Review & Run Verification/i }));
    await waitFor(() => screen.getByRole('heading', { name: /Confirm Repository Code Execution/i }));

    fireEvent.click(screen.getByLabelText(/I acknowledge and approve executing repository test code/i));
    fireEvent.click(screen.getByRole('button', { name: /Confirm & Execute Verification/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Verification Request Failed \[SERVICE_UNAVAILABLE\]/i)
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText('Verification service unavailable on server.')
    ).toBeInTheDocument();
  });
});
