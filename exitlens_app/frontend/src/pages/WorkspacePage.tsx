import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderGit2,
  Globe,
  Sliders,
  AlertCircle,
  Clock,
  ShieldCheck,
  CheckCircle2,
  Cpu,
  Layers,
  Info,
  RefreshCw,
  ArrowRight,
  RotateCcw,
  AlertTriangle,
  HardDrive,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { SegmentedControl } from '../components/ui/SegmentedControl';
import { StatusBadge, StatusVariant } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { useAnalysisContext } from '../context/useAnalysisContext';
import { RepositoryKind, RunStatus } from '../types/api';

export function WorkspacePage() {
  const navigate = useNavigate();
  const {
    health,
    activeAnalysis,
    isSubmitting,
    isPolling,
    submissionError,
    recentRuns,
    startAnalysis,
    clearSubmissionError,
    selectRun,
    resetActiveAnalysis,
  } = useAnalysisContext();

  const [sourceKind, setSourceKind] = useState<RepositoryKind>('local_path');
  const [repoValue, setRepoValue] = useState('');
  const [includeTests, setIncludeTests] = useState(true);
  const [useGitHistory, setUseGitHistory] = useState(true);
  const [generateRecommendations, setGenerateRecommendations] = useState(true);
  const [localValidationError, setLocalValidationError] = useState<string | null>(null);

  const getStatusVariant = (status: RunStatus): StatusVariant => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'completed_with_warnings':
      case 'ready_for_verification':
        return 'warning';
      case 'failed':
        return 'failure';
      case 'queued':
      case 'validating_repository':
      case 'scanning':
      case 'mapping_usage':
      case 'assessing_risk':
      case 'generating_recommendations':
      case 'verifying':
        return 'info';
      default:
        return 'neutral';
    }
  };

  const formatStageLabel = (stage: string) => {
    return stage
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalValidationError(null);
    clearSubmissionError();

    const trimmed = repoValue.trim();
    if (!trimmed) {
      setLocalValidationError(
        sourceKind === 'local_path'
          ? 'Please enter a valid local repository directory path.'
          : 'Please enter a valid public HTTPS Git repository URL.'
      );
      return;
    }

    if (sourceKind === 'git_url') {
      try {
        const url = new URL(trimmed);
        if (url.protocol !== 'https:') {
          setLocalValidationError('Only secure HTTPS Git URLs are supported.');
          return;
        }
      } catch {
        setLocalValidationError('Invalid URL format. Please provide a valid HTTPS Git URL.');
        return;
      }
    }

    await startAnalysis({
      repository: {
        kind: sourceKind,
        value: trimmed,
        git_ref: null,
      },
      options: {
        exclude_paths: ['.git', '.venv', 'venv', 'node_modules', 'reports', 'exitlens_app'],
        include_tests: includeTests,
        use_git_history: useGitHistory,
        generate_recommendations: generateRecommendations,
      },
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Repository Workspace"
        description="Inspect dependency maintenance risks, trace actual usage, and prepare evidence-linked migration plans."
        badge={
          <StatusBadge
            variant={health.isBackendAvailable ? (health.isModelAvailable ? 'success' : 'warning') : 'neutral'}
            size="sm"
            dot
          >
            {health.isBackendAvailable
              ? health.isModelAvailable
                ? 'Backend & Gemma 4 Ready'
                : 'Backend Connected · Model Offline'
              : 'Backend Offline'}
          </StatusBadge>
        }
        breadcrumbs={[
          { label: 'Workbench' },
          { label: 'Workspace' },
        ]}
      />

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Repository Submission / Active Run Monitoring */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {/* Active Run Card if active analysis exists */}
          {activeAnalysis ? (
            <Panel
              title={
                <div className="flex items-center gap-2">
                  <span>Active Analysis Run</span>
                  <StatusBadge
                    variant={getStatusVariant(activeAnalysis.status)}
                    size="sm"
                    dot={isPolling}
                  >
                    {formatStageLabel(activeAnalysis.status)}
                  </StatusBadge>
                </div>
              }
              subtitle={
                <span className="font-mono text-xs text-[#526176]">
                  ID: {activeAnalysis.analysis_id}
                </span>
              }
              actions={
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={resetActiveAnalysis}
                    icon={<RotateCcw className="w-3.5 h-3.5" />}
                  >
                    New Scan
                  </Button>
                </div>
              }
            >
              <div className="flex flex-col gap-4">
                {/* Repository details */}
                <div className="p-3 bg-[#F5F7FA] border border-[#E1E6EE] rounded-md flex flex-col gap-1 text-xs">
                  <div className="flex items-center justify-between text-[#526176]">
                    <span>Target Repository:</span>
                    <span className="font-medium text-[#172033] font-mono truncate max-w-sm">
                      {activeAnalysis.repository?.value || 'Active Workspace'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[#718096]">
                    <span>Created:</span>
                    <span>{new Date(activeAnalysis.created_at).toLocaleTimeString()}</span>
                  </div>
                </div>

                {/* Live stage tracking */}
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-[#172033]">Current Execution Stage:</span>
                    <span className="font-mono text-[#315BE8] font-semibold">
                      {formatStageLabel(activeAnalysis.stage || activeAnalysis.status)}
                    </span>
                  </div>

                  {isPolling && (
                    <div className="p-3 bg-[#EEF3FF] border border-[#C6D8FF] rounded-md text-xs text-[#2648C7] flex items-center gap-2">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#315BE8] shrink-0" />
                      <span>
                        Analysis in progress. Polling status from FastAPI backend...
                      </span>
                    </div>
                  )}

                  {!isPolling && (activeAnalysis.status === 'completed' || activeAnalysis.status === 'ready_for_verification') && (
                    <div className="p-3 bg-[#EAF7EF] border border-[#C8ECCF] rounded-md text-xs text-[#18794E] flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#18794E] shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">Analysis Complete:</span> Findings and evidence are ready for inspection in the Dependency Inventory.
                      </div>
                    </div>
                  )}

                  {activeAnalysis.status === 'failed' && (
                    <div className="p-3 bg-[#FEF0F0] border border-[#FECDCA] rounded-md text-xs text-[#B42318] flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-[#B42318] shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">Analysis Failed:</span> The backend encountered an error while scanning the repository.
                      </div>
                    </div>
                  )}
                </div>

                {/* Summary counts if provided by backend */}
                {activeAnalysis.summary && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-[#E1E6EE] text-center">
                    <div className="p-2 bg-[#F5F7FA] rounded border border-[#E1E6EE]">
                      <div className="text-lg font-bold text-[#172033]">
                        {activeAnalysis.summary.dependencies_discovered}
                      </div>
                      <div className="text-[10px] text-[#718096] uppercase">Discovered</div>
                    </div>
                    <div className="p-2 bg-[#F5F7FA] rounded border border-[#E1E6EE]">
                      <div className="text-lg font-bold text-[#B42318]">
                        {activeAnalysis.summary.dependencies_flagged}
                      </div>
                      <div className="text-[10px] text-[#718096] uppercase">Flagged Risks</div>
                    </div>
                    <div className="p-2 bg-[#F5F7FA] rounded border border-[#E1E6EE]">
                      <div className="text-lg font-bold text-[#315BE8]">
                        {activeAnalysis.summary.recommendations_available}
                      </div>
                      <div className="text-[10px] text-[#718096] uppercase">Gemma 4 Plans</div>
                    </div>
                    <div className="p-2 bg-[#F5F7FA] rounded border border-[#E1E6EE]">
                      <div className="text-lg font-bold text-[#18794E]">
                        {activeAnalysis.summary.checks_passed}
                      </div>
                      <div className="text-[10px] text-[#718096] uppercase">Passed Checks</div>
                    </div>
                  </div>
                )}

                {/* Warnings list if any */}
                {activeAnalysis.warnings && activeAnalysis.warnings.length > 0 && (
                  <div className="p-3 bg-[#FFF5DE] border border-[#FDE4A4] rounded-md text-xs text-[#925C08] flex flex-col gap-1">
                    <span className="font-semibold flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" /> Scanner Coverage Notes:
                    </span>
                    <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                      {activeAnalysis.warnings.map((w, idx) => (
                        <li key={idx}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Primary Transition Action */}
                <div className="pt-3 border-t border-[#E1E6EE] flex items-center justify-between">
                  <span className="text-xs text-[#526176]">
                    Navigate to inventory to view evidence.
                  </span>
                  <Button
                    variant="primary"
                    size="md"
                    onClick={() => navigate('/analysis')}
                    icon={<ArrowRight className="w-4 h-4" />}
                    iconPosition="right"
                  >
                    View Analysis in Inventory
                  </Button>
                </div>
              </div>
            </Panel>
          ) : (
            /* Submission Form Panel */
            <Panel
              title="Repository Source & Scope"
              subtitle="Specify the Python repository to inspect for dependency risks and migration feasibility."
            >
              <form onSubmit={handleSubmit} className="flex flex-col gap-5">
                {/* Submission Error Banner */}
                {submissionError && (
                  <div className="p-3.5 bg-[#FEF0F0] border border-[#FECDCA] rounded-md text-xs text-[#B42318] flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-[#B42318] shrink-0 mt-0.5" />
                    <div className="flex-1 flex flex-col gap-1">
                      <span className="font-semibold">
                        Request Failed [{submissionError.code}]
                      </span>
                      <span className="leading-relaxed">{submissionError.message}</span>
                      {submissionError.code === 'NETWORK_ERROR' && (
                        <span className="text-[11px] text-[#526176] mt-1">
                          Tip: Start the FastAPI backend with:{' '}
                          <code className="px-1 py-0.5 bg-[#EEF1F5] rounded font-mono text-[#172033]">
                            uvicorn app.main:app --reload --port 8000
                          </code>
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Source Selection Segment */}
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-semibold text-[#172033] tracking-tight uppercase">
                    Repository Source Type
                  </label>
                  <SegmentedControl<RepositoryKind>
                    value={sourceKind}
                    onChange={(val) => {
                      setSourceKind(val);
                      setLocalValidationError(null);
                      clearSubmissionError();
                    }}
                    options={[
                      {
                        value: 'local_path',
                        label: 'Local Repository Path',
                        icon: <FolderGit2 className="w-3.5 h-3.5" />,
                      },
                      {
                        value: 'git_url',
                        label: 'Public HTTPS Git URL',
                        icon: <Globe className="w-3.5 h-3.5" />,
                      },
                    ]}
                  />
                </div>

                {/* Repository Input */}
                <Input
                  label={sourceKind === 'local_path' ? 'Local Directory Path' : 'Git Repository URL'}
                  value={repoValue}
                  onChange={(e) => {
                    setRepoValue(e.target.value);
                    if (localValidationError) setLocalValidationError(null);
                    if (submissionError) clearSubmissionError();
                  }}
                  placeholder={
                    sourceKind === 'local_path'
                      ? 'e.g., C:\\work\\LinkWatch or /home/developer/LinkWatch'
                      : 'e.g., https://github.com/rishrek/LinkWatch.git'
                  }
                  error={localValidationError || undefined}
                  helperText={
                    sourceKind === 'local_path' ? (
                      <span className="flex items-start gap-1">
                        <Info className="w-3.5 h-3.5 text-[#718096] shrink-0 mt-0.5" />
                        <span>
                          Local paths are resolved on the host machine by the ExitLens FastAPI backend within configured allowed roots.
                        </span>
                      </span>
                    ) : (
                      <span>
                        Public HTTPS repository. The backend will perform a shallow clone into a disposable analysis workspace.
                      </span>
                    )
                  }
                />

                {/* Analysis Options Section */}
                <div className="pt-4 border-t border-[#E1E6EE] flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-[#718096]" />
                    <span className="text-xs font-semibold text-[#172033] uppercase tracking-tight">
                      Analysis Options
                    </span>
                  </div>

                  <div className="space-y-3">
                    <label className="flex items-start gap-3 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={includeTests}
                        onChange={(e) => setIncludeTests(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-[#E1E6EE] text-[#315BE8] focus:ring-[#315BE8]"
                      />
                      <div className="flex flex-col text-xs">
                        <span className="font-medium text-[#172033]">
                          Include tests in static usage mapping
                        </span>
                        <span className="text-[#526176]">
                          Inspect test files to distinguish test-only dependency imports from core production usage.
                        </span>
                      </div>
                    </label>

                    <label className="flex items-start gap-3 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={useGitHistory}
                        onChange={(e) => setUseGitHistory(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-[#E1E6EE] text-[#315BE8] focus:ring-[#315BE8]"
                      />
                      <div className="flex flex-col text-xs">
                        <span className="font-medium text-[#172033]">
                          Use Git history when available
                        </span>
                        <span className="text-[#526176]">
                          Extract repository commit revision and recent change timestamps to assess maintenance recency.
                        </span>
                      </div>
                    </label>

                    <label className="flex items-start gap-3 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={generateRecommendations}
                        onChange={(e) => setGenerateRecommendations(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-[#E1E6EE] text-[#315BE8] focus:ring-[#315BE8]"
                      />
                      <div className="flex flex-col text-xs">
                        <span className="font-medium text-[#172033]">
                          Generate Gemma 4 recommendations
                        </span>
                        <span className="text-[#526176]">
                          Produce structured migration candidates, replacement rationale, and suggested test profiles using local Gemma 4 inference.
                        </span>
                      </div>
                    </label>
                  </div>
                </div>

                {/* Action Area */}
                <div className="pt-4 border-t border-[#E1E6EE] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-1.5 text-xs text-[#526176]">
                    <ShieldCheck className="w-3.5 h-3.5 text-[#718096] shrink-0" />
                    <span>Non-executing static analysis of dependencies & manifests.</span>
                  </div>

                  <Button
                    type="submit"
                    size="md"
                    isLoading={isSubmitting}
                    disabled={isSubmitting || !repoValue.trim()}
                    icon={<FolderGit2 className="w-4 h-4" />}
                  >
                    Analyze Repository
                  </Button>
                </div>
              </form>
            </Panel>
          )}
        </div>

        {/* Right Column: Connection Readiness, Coverage & History */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {/* Connection Readiness Panel */}
          <Panel
            title="System & Readiness Status"
            subtitle="Live status from FastAPI health endpoint."
            actions={
              <button
                type="button"
                onClick={() => health.refetch()}
                className="p-1 rounded text-[#718096] hover:text-[#172033] hover:bg-[#EEF1F5] transition-colors"
                title="Refresh health status"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${health.isLoading ? 'animate-spin' : ''}`} />
              </button>
            }
          >
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between py-1.5 border-b border-[#E1E6EE]">
                <div className="flex items-center gap-2 text-[#526176]">
                  <Cpu className="w-4 h-4 text-[#718096]" />
                  <span>FastAPI Backend</span>
                </div>
                {health.isLoading ? (
                  <StatusBadge variant="neutral" size="sm" dot>
                    Checking...
                  </StatusBadge>
                ) : health.isBackendAvailable ? (
                  <StatusBadge variant="success" size="sm" dot>
                    Available
                  </StatusBadge>
                ) : (
                  <StatusBadge variant="failure" size="sm" dot>
                    Unavailable
                  </StatusBadge>
                )}
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-[#E1E6EE]">
                <div className="flex items-center gap-2 text-[#526176]">
                  <Layers className="w-4 h-4 text-[#718096]" />
                  <span>Gemma 4 (Local Ollama)</span>
                </div>
                {health.isLoading ? (
                  <StatusBadge variant="neutral" size="sm">
                    Checking...
                  </StatusBadge>
                ) : health.isModelAvailable ? (
                  <StatusBadge variant="success" size="sm">
                    {health.data?.model?.configured_id || 'Ready'}
                  </StatusBadge>
                ) : health.isBackendAvailable ? (
                  <StatusBadge variant="warning" size="sm">
                    Model Offline
                  </StatusBadge>
                ) : (
                  <StatusBadge variant="neutral" size="sm">
                    Unknown
                  </StatusBadge>
                )}
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-[#E1E6EE]">
                <div className="flex items-center gap-2 text-[#526176]">
                  <ShieldCheck className="w-4 h-4 text-[#718096]" />
                  <span>Python Runtime</span>
                </div>
                <span className="font-mono text-[#172033] font-medium">
                  {health.data?.python_version || 'Target: Python 3.12 / 3.13'}
                </span>
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-[#E1E6EE]">
                <div className="flex items-center gap-2 text-[#526176]">
                  <HardDrive className="w-4 h-4 text-[#718096]" />
                  <span>Run Storage</span>
                </div>
                <span className="font-medium text-[#172033]">
                  {health.isBackendAvailable ? 'Filesystem / Active' : 'Pending Server'}
                </span>
              </div>

              {health.error && (
                <div className="p-2.5 bg-[#FEF0F0] border border-[#FECDCA] rounded text-[11px] text-[#B42318] leading-normal flex items-start gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{health.error}</span>
                </div>
              )}
            </div>
          </Panel>

          {/* Recent Runs Panel */}
          <Panel
            title="Recent Analysis Runs"
            subtitle="Scans stored from this workbench session."
          >
            {recentRuns.length > 0 ? (
              <div className="flex flex-col divide-y divide-[#E1E6EE] -my-1">
                {recentRuns.map((run) => (
                  <div
                    key={run.analysisId}
                    className="py-2.5 flex items-center justify-between text-xs hover:bg-[#F5F7FA] px-1 rounded transition-colors"
                  >
                    <div className="flex flex-col gap-0.5 min-w-0 pr-2">
                      <span className="font-medium text-[#172033] truncate max-w-xs font-mono">
                        {run.repositoryValue}
                      </span>
                      <span className="text-[10px] text-[#718096]">
                        {new Date(run.createdAt).toLocaleString()} · ID: {run.analysisId.slice(0, 8)}...
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <StatusBadge
                        variant={getStatusVariant(run.status)}
                        size="sm"
                      >
                        {formatStageLabel(run.status)}
                      </StatusBadge>
                      <button
                        type="button"
                        onClick={() => selectRun(run.analysisId)}
                        className="text-xs text-[#315BE8] hover:underline font-medium"
                      >
                        Open
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                compact
                icon={<Clock className="w-5 h-5" />}
                title="No Analysis Runs Recorded Yet"
                description="Submitted repository scans will be listed here with live stage updates and direct links."
              />
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
