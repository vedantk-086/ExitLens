import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { WorkspacePage } from '../src/pages/WorkspacePage';
import { AnalysisProvider } from '../src/context/AnalysisContext';
import * as healthApi from '../src/api/health';
import * as analysesApi from '../src/api/analyses';
import { ApiClientError } from '../src/api/client';

describe('WorkspacePage Component with Backend Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  const renderWorkspace = () =>
    render(
      <BrowserRouter>
        <AnalysisProvider>
          <WorkspacePage />
        </AnalysisProvider>
      </BrowserRouter>
    );

  it('renders page header and explanatory supporting text', async () => {
    vi.spyOn(healthApi, 'getHealth').mockResolvedValue({
      status: 'ok',
      api_ready: true,
      python_version: '3.13.2',
      model: { configured_id: 'gemma4', ready: true },
    });

    renderWorkspace();
    expect(screen.getByRole('heading', { level: 1, name: /repository workspace/i })).toBeInTheDocument();
    expect(
      screen.getByText(/inspect dependency maintenance risks, trace actual usage, and prepare evidence-linked migration plans/i)
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/backend & gemma 4 ready/i)).toBeInTheDocument();
    });
  });

  it('allows toggling between local path and git URL', async () => {
    vi.spyOn(healthApi, 'getHealth').mockRejectedValue(new Error('Offline'));
    renderWorkspace();

    await waitFor(() => {
      expect(screen.getByText('Backend Offline')).toBeInTheDocument();
    });

    const localOption = screen.getByRole('radio', { name: /local repository path/i });
    const gitOption = screen.getByRole('radio', { name: /public https git url/i });

    expect(localOption).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByPlaceholderText(/e\.g\., C:\\work\\LinkWatch or \/home\/developer\/LinkWatch/i)).toBeInTheDocument();

    fireEvent.click(gitOption);
    expect(gitOption).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByPlaceholderText(/e\.g\., https:\/\/github\.com\/rishrek\/LinkWatch\.git/i)).toBeInTheDocument();
  });

  it('displays honest offline state when backend is not responding', async () => {
    vi.spyOn(healthApi, 'getHealth').mockRejectedValue(
      new ApiClientError('Unable to connect to ExitLens backend at http://127.0.0.1:8000/api/v1.', 0, 'NETWORK_ERROR')
    );

    renderWorkspace();

    await waitFor(() => {
      expect(screen.getByText('Backend Offline')).toBeInTheDocument();
      expect(screen.getByText('Unavailable')).toBeInTheDocument();
    });
  });

  it('handles backend submission failure gracefully and displays error details', async () => {
    vi.spyOn(healthApi, 'getHealth').mockResolvedValue({
      status: 'ok',
      api_ready: true,
    });
    vi.spyOn(analysesApi, 'createAnalysis').mockRejectedValue(
      new ApiClientError('Local repository path was not found.', 404, 'REPOSITORY_NOT_FOUND')
    );

    renderWorkspace();

    const input = screen.getByPlaceholderText(/e\.g\., C:\\work\\LinkWatch/i);
    fireEvent.change(input, { target: { value: 'C:\\invalid\\path' } });

    const submitBtn = screen.getByRole('button', { name: /analyze repository/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/request failed \[REPOSITORY_NOT_FOUND\]/i)).toBeInTheDocument();
      expect(screen.getByText(/local repository path was not found/i)).toBeInTheDocument();
    });
  });

  it('submits repository and begins polling progress until completion', async () => {
    vi.spyOn(healthApi, 'getHealth').mockResolvedValue({
      status: 'ok',
      api_ready: true,
      model: { configured_id: 'gemma4', ready: true },
    });

    vi.spyOn(analysesApi, 'createAnalysis').mockResolvedValue({
      analysis_id: 'test-analysis-1234',
      status: 'queued',
      stage: 'validating_repository',
      created_at: new Date().toISOString(),
    });

    vi.spyOn(analysesApi, 'getAnalysis').mockResolvedValue({
      analysis_id: 'test-analysis-1234',
      status: 'completed',
      stage: 'completed',
      created_at: new Date().toISOString(),
      summary: {
        dependencies_discovered: 12,
        dependencies_flagged: 3,
        recommendations_available: 3,
        baseline_checks: 1,
        replacement_checks: 1,
        checks_passed: 1,
        checks_failed: 0,
        checks_skipped_or_unverified: 0,
      },
      warnings: [],
      errors: [],
    });

    renderWorkspace();

    const input = screen.getByPlaceholderText(/e\.g\., C:\\work\\LinkWatch/i);
    fireEvent.change(input, { target: { value: 'C:\\work\\LinkWatch' } });

    const submitBtn = screen.getByRole('button', { name: /analyze repository/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/id: test-analysis-1234/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /view analysis in inventory/i })).toBeInTheDocument();
    });
  });
});
