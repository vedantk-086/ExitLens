/**
 * ExitLens — Step 3 tests
 * Analysis page: inventory rendering, states, filtering, drawer, recommendation retry.
 * Tests run against mocked API — backend is not required to be live.
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
  createAnalysis: vi.fn(),
  getAnalysis: vi.fn(),
}));
vi.mock('../src/api/health', () => ({ getHealth: vi.fn() }));

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
  selectedDependencyIds: [],
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
    repository: { kind: 'local_path' as const, value: '/repo' },
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

function makeDetail() {
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
    usage_locations: [
      {
        file_path: 'src/client.py',
        line_start: 3,
        excerpt: 'import requests',
        provenance: 'OBSERVED' as const,
      },
    ],
    proposed_replacement: {
      status: 'available',
      candidate_distribution: 'httpx',
      candidate_specifier: '>=0.24.0',
      rationale: 'httpx is a modern async-capable HTTP client.',
      provenance: 'AI_RECOMMENDATION' as const,
    },
    migration_steps: [
      {
        step_number: 1,
        description: 'Replace requests.get with httpx.get',
        provenance: 'AI_RECOMMENDATION' as const,
      },
    ],
    suggested_tests: [],
    executed_test_results: [],
    compatibility_gaps: [],
    open_concerns_limitations: [
      { description: 'Async usage patterns differ; review await syntax.' },
    ],
  };
}

// ─── Render helper ───────────────────────────────────────────────────────────

import { AnalysisPage } from '../src/pages/AnalysisPage';

function renderAnalysisPage() {
  return render(
    <MemoryRouter>
      <AnalysisPage />
    </MemoryRouter>
  );
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('AnalysisPage — no active analysis', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = null;
    vi.clearAllMocks();
  });

  it('renders the empty/no-analysis state and a workspace link', () => {
    renderAnalysisPage();
    expect(screen.getByText('No Active Repository Analysis')).toBeInTheDocument();
    expect(screen.getByText('Configure Repository Scan')).toBeInTheDocument();
  });
});

describe('AnalysisPage — analysis still running', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis('scanning') as never;
    mockContext.isPolling = true;
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [],
    });
  });

  it('shows in-progress banner', () => {
    renderAnalysisPage();
    expect(screen.getByText(/Analysis in progress/)).toBeInTheDocument();
  });

  it('does not call getDependencies while still running', () => {
    renderAnalysisPage();
    expect(analysesApi.getDependencies).not.toHaveBeenCalled();
  });
});

describe('AnalysisPage — inventory loaded', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis('completed') as never;
    mockContext.isPolling = false;
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [
        makeDep(),
        makeDep({
          dependency_id: 'dep-002',
          name: 'flask',
          highest_severity: 'medium',
          risk_rule_ids: ['MANIFEST_LOCK_DRIFT'],
        }),
      ],
      warnings: [],
    });
  });

  it('renders summary counts from context', async () => {
    renderAnalysisPage();
    // Summary strip shows values from activeAnalysis.summary
    await waitFor(() => expect(screen.getByText('10')).toBeInTheDocument());
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders dependency rows', async () => {
    renderAnalysisPage();
    await waitFor(() => expect(screen.getByText('requests')).toBeInTheDocument());
    expect(screen.getByText('flask')).toBeInTheDocument();
  });

  it('filters by search query', async () => {
    renderAnalysisPage();
    await waitFor(() => expect(screen.getByText('requests')).toBeInTheDocument());
    const input = screen.getByPlaceholderText('Search name, manifest, rule…');
    fireEvent.change(input, { target: { value: 'flask' } });
    expect(screen.queryByText('requests')).not.toBeInTheDocument();
    expect(screen.getByText('flask')).toBeInTheDocument();
  });

  it('shows no-match state when filter eliminates all rows', async () => {
    renderAnalysisPage();
    await waitFor(() => expect(screen.getByText('requests')).toBeInTheDocument());
    const input = screen.getByPlaceholderText('Search name, manifest, rule…');
    fireEvent.change(input, { target: { value: 'nonexistent-xyz' } });
    expect(screen.getByText('No Matching Dependencies')).toBeInTheDocument();
  });
});

describe('AnalysisPage — empty inventory', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis('completed') as never;
    mockContext.isPolling = false;
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [],
    });
  });

  it('shows the no-dependencies empty state', async () => {
    renderAnalysisPage();
    await waitFor(() =>
      expect(screen.getByText('No Dependencies Discovered')).toBeInTheDocument()
    );
  });
});

describe('AnalysisPage — inventory error', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis('completed') as never;
    mockContext.isPolling = false;
    vi.clearAllMocks();
  });

  it('shows inventory error state with message', async () => {
    const { ApiClientError } = await import('../src/api/client');
    vi.mocked(analysesApi.getDependencies).mockRejectedValue(
      new ApiClientError('Backend unreachable', 0, 'NETWORK_ERROR')
    );
    renderAnalysisPage();
    await waitFor(() =>
      expect(screen.getByText(/Inventory Unavailable/)).toBeInTheDocument()
    );
    expect(screen.getByText('Backend unreachable')).toBeInTheDocument();
  });
});

describe('AnalysisPage — dependency detail drawer', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis('completed') as never;
    mockContext.isPolling = false;
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [makeDep()],
    });
    vi.mocked(analysesApi.getDependencyDetail).mockResolvedValue(makeDetail() as never);
  });

  it('opens the drawer when a row inspect button is clicked', async () => {
    renderAnalysisPage();
    await waitFor(() => expect(screen.getByText('requests')).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText('Inspect requests'));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
    expect(analysesApi.getDependencyDetail).toHaveBeenCalledWith(
      'test-analysis-001',
      'dep-001'
    );
  });

  it('renders all nine section headings in the drawer', async () => {
    renderAnalysisPage();
    await waitFor(() => screen.getByText('requests'));
    fireEvent.click(screen.getByLabelText('Inspect requests'));
    await waitFor(() => expect(screen.getByText('Risk Indicators')).toBeInTheDocument());
    expect(screen.getByText('Usage Locations')).toBeInTheDocument();
    expect(screen.getByText('Proposed Replacement')).toBeInTheDocument();
    expect(screen.getByText('Migration Steps')).toBeInTheDocument();
    expect(screen.getByText('Suggested Tests')).toBeInTheDocument();
    expect(screen.getByText('Executed Test Results')).toBeInTheDocument();
    expect(screen.getByText('Compatibility Gaps')).toBeInTheDocument();
    expect(screen.getByText(/Open Concerns/)).toBeInTheDocument();
  });

  it('shows unavailable message for empty executed results', async () => {
    renderAnalysisPage();
    await waitFor(() => screen.getByText('requests'));
    fireEvent.click(screen.getByLabelText('Inspect requests'));
    await waitFor(() =>
      expect(
        screen.getByText(/Not run — no verification trials have been executed/)
      ).toBeInTheDocument()
    );
  });

  it('closes drawer on Escape key (slides out via CSS)', async () => {
    renderAnalysisPage();
    await waitFor(() => screen.getByText('requests'));
    fireEvent.click(screen.getByLabelText('Inspect requests'));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
    // Drawer is open: translate-x-0
    expect(screen.getByRole('dialog').className).toContain('translate-x-0');
    fireEvent.keyDown(document, { key: 'Escape' });
    // After Escape, drawer slides out: translate-x-full
    await waitFor(() =>
      expect(screen.getByRole('dialog').className).toContain('translate-x-full')
    );
  });
});

describe('AnalysisPage — recommendation retry', () => {
  beforeEach(() => {
    mockContext.activeAnalysis = makeAnalysis('completed') as never;
    mockContext.isPolling = false;
    vi.clearAllMocks();
    vi.mocked(analysesApi.getDependencies).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      dependencies: [makeDep()],
    });
    vi.mocked(analysesApi.postRecommendations).mockResolvedValue({
      analysis_id: 'test-analysis-001',
      status: 'queued',
      queued_count: 1,
    });
  });

  it('shows retry panel when a dependency is selected', async () => {
    renderAnalysisPage();
    await waitFor(() => screen.getByText('requests'));
    const checkbox = screen.getByLabelText('Select requests');
    fireEvent.click(checkbox);
    await waitFor(() =>
      expect(screen.getByText('Retry Recommendations')).toBeInTheDocument()
    );
  });

  it('submits the documented recommendation request payload', async () => {
    renderAnalysisPage();
    await waitFor(() => screen.getByText('requests'));
    fireEvent.click(screen.getByLabelText('Select requests'));
    await waitFor(() => screen.getByText('Retry Recommendations'));
    fireEvent.click(screen.getByText('Retry Recommendations'));
    await waitFor(() => {
      expect(analysesApi.postRecommendations).toHaveBeenCalledWith(
        'test-analysis-001',
        { dependency_ids: ['dep-001'], force_regenerate: false }
      );
    });
  });
});
