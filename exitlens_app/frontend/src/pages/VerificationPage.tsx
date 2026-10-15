import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ShieldCheck,
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  MinusCircle,
  Terminal,
  Play,
  FileCode,
  Lock,
  Globe,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  Loader2,
  RotateCcw,
  Package,
  PackageCheck,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge, StatusVariant } from '../components/ui/StatusBadge';
import { useAnalysisContext } from '../context/useAnalysisContext';
import { useDependencyList, useDependencyDetail } from '../hooks/useDependencies';
import { postVerification, getTestProfiles } from '../api/analyses';
import { ApiClientError } from '../api/client';
import {
  VerificationRequest,
  VerificationResponse,
  VerificationExecutionRecord,
  VerificationStatus,
  RiskSeverity,
  TestProfile,
} from '../types/api';

// ─── Constants ───────────────────────────────────────────────────────────────

const DEFAULT_TIMEOUT_SECONDS = 90;
const MIN_TIMEOUT_SECONDS = 10;
const MAX_TIMEOUT_SECONDS = 180;

// ─── Status Variant Helper ───────────────────────────────────────────────────

function getExecutionStatusVariant(status?: VerificationStatus | string | null): StatusVariant {
  switch (status?.toUpperCase()) {
    case 'PASSED':
      return 'success';
    case 'FAILED':
    case 'ERROR':
      return 'failure';
    case 'TIMED_OUT':
      return 'warning';
    case 'SKIPPED':
    case 'NOT_RUN':
    default:
      return 'neutral';
  }
}

function getExecutionStatusIcon(status?: VerificationStatus | string | null) {
  switch (status?.toUpperCase()) {
    case 'PASSED':
      return <CheckCircle2 className="w-4 h-4 text-[#18794E]" />;
    case 'FAILED':
      return <XCircle className="w-4 h-4 text-[#B42318]" />;
    case 'ERROR':
      return <AlertCircle className="w-4 h-4 text-[#B42318]" />;
    case 'TIMED_OUT':
      return <Clock className="w-4 h-4 text-[#925C08]" />;
    case 'SKIPPED':
    case 'NOT_RUN':
    default:
      return <MinusCircle className="w-4 h-4 text-[#718096]" />;
  }
}

function severityVariant(severity?: RiskSeverity | null): StatusVariant {
  switch (severity?.toLowerCase()) {
    case 'critical':
    case 'high':
      return 'failure';
    case 'medium':
      return 'warning';
    case 'low':
      return 'info';
    default:
      return 'neutral';
  }
}

// ─── Bounded Output Component ────────────────────────────────────────────────

function BoundedOutputView({ label, content }: { label: string; content?: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!content) return null;

  const isLong = content.length > 300 || content.split('\n').length > 8;
  const displayContent = !expanded && isLong
    ? content.slice(0, 300) + '...\n[Output truncated — click expand to view full log]'
    : content;

  return (
    <div className="flex flex-col gap-1 text-xs">
      <div className="flex items-center justify-between text-[#526176]">
        <span className="font-mono text-[11px] font-medium uppercase tracking-wider">{label}</span>
        {isLong && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-[11px] text-[#315BE8] hover:underline"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {expanded ? 'Collapse' : 'Expand full output'}
          </button>
        )}
      </div>
      <pre className="text-[11px] font-mono bg-[#172033] text-[#E2E8F0] p-3 rounded-md overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
        {displayContent}
      </pre>
    </div>
  );
}

// ─── Result Card Component ───────────────────────────────────────────────────

interface ExecutionCardProps {
  title: string;
  subtitle: string;
  isBaseline: boolean;
  record?: VerificationExecutionRecord | null;
  fallbackStatus?: VerificationStatus;
  fallbackReason?: string;
  profileId?: string;
}

function ExecutionCard({
  title,
  subtitle,
  isBaseline,
  record,
  fallbackStatus = 'NOT_RUN',
  fallbackReason,
  profileId,
}: ExecutionCardProps) {
  const status: VerificationStatus | string = record?.status || fallbackStatus;
  const variant = getExecutionStatusVariant(status);
  const icon = getExecutionStatusIcon(status);

  return (
    <div className="border border-[#E1E6EE] rounded-lg bg-white overflow-hidden flex flex-col h-full shadow-xs">
      {/* Header */}
      <div className="px-4 py-3 bg-[#F5F7FA] border-b border-[#E1E6EE] flex items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-[#172033]">{title}</h3>
            <span className="text-[11px] font-mono text-[#718096] px-1.5 py-0.5 rounded bg-[#E1E6EE]">
              {isBaseline ? 'Baseline' : 'Replacement Candidate'}
            </span>
          </div>
          <p className="text-xs text-[#718096] mt-0.5">{subtitle}</p>
        </div>
        <StatusBadge variant={variant} size="md" icon={icon}>
          {status}
        </StatusBadge>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col gap-4 text-xs">
        {/* Profile ID & Command Args */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-[#FAFBFC] p-3 rounded-md border border-[#E1E6EE]">
          <div>
            <span className="text-[#718096] block text-[11px]">Test Profile ID</span>
            <span className="font-mono font-medium text-[#172033] break-all">
              {record?.profile_id || profileId || (isBaseline ? 'server-detected-baseline' : 'server-detected-replacement')}
            </span>
          </div>
          <div>
            <span className="text-[#718096] block text-[11px]">Exit Code</span>
            <span className="font-mono font-medium text-[#172033]">
              {record?.exit_code !== undefined && record?.exit_code !== null ? record.exit_code : '—'}
            </span>
          </div>
          <div className="sm:col-span-2">
            <span className="text-[#718096] block text-[11px]">Command / Args</span>
            <span className="font-mono text-[11px] text-[#526176] break-all">
              {record?.command || (record?.command_args ? record.command_args.join(' ') : 'allow-listed pytest runner')}
            </span>
          </div>
        </div>

        {/* Timing Information */}
        <div className="flex items-center gap-4 text-xs text-[#526176] border-b border-[#E1E6EE] pb-3">
          <div>
            <span className="text-[#718096]">Duration: </span>
            <span className="font-semibold text-[#172033]">
              {record?.duration_seconds != null ? `${record.duration_seconds.toFixed(2)}s` : '—'}
            </span>
          </div>
          {record?.start_time && (
            <div>
              <span className="text-[#718096]">Started: </span>
              <span className="font-mono text-[11px]">{new Date(record.start_time).toLocaleTimeString()}</span>
            </div>
          )}
          {record?.end_time && (
            <div>
              <span className="text-[#718096]">Ended: </span>
              <span className="font-mono text-[11px]">{new Date(record.end_time).toLocaleTimeString()}</span>
            </div>
          )}
        </div>

        {/* Status notice if not run / skipped / error */}
        {status === 'NOT_RUN' && (
          <div className="p-3 bg-[#EEF1F5] rounded-md text-[#526176] text-xs">
            <span className="font-semibold block mb-0.5">Execution Status: NOT_RUN</span>
            <span>{fallbackReason || 'Test execution has not yet been triggered for this environment.'}</span>
          </div>
        )}

        {status === 'SKIPPED' && (
          <div className="p-3 bg-[#FFF5DE] border border-[#FDE4A4] rounded-md text-[#925C08] text-xs">
            <span className="font-semibold block mb-0.5">Trial Skipped</span>
            <span>{record?.skip_reason || fallbackReason || 'Execution was skipped by policy or lack of cached candidate.'}</span>
          </div>
        )}

        {status === 'TIMED_OUT' && (
          <div className="p-3 bg-[#FFF5DE] border border-[#FDE4A4] rounded-md text-[#925C08] text-xs">
            <span className="font-semibold block mb-0.5">Execution Timed Out</span>
            <span>{record?.error_reason || 'Test execution exceeded the configured timeout limit.'}</span>
          </div>
        )}

        {status === 'ERROR' && (
          <div className="p-3 bg-[#FEF0F0] border border-[#FECDCA] rounded-md text-[#B42318] text-xs">
            <span className="font-semibold block mb-0.5">Execution Error</span>
            <span>{record?.error_reason || 'An execution environment error occurred.'}</span>
          </div>
        )}

        {/* Runtime differences */}
        {record?.runtime_differences && (
          <div className="p-3 bg-[#EEF3FF] border border-[#C6D8FF] rounded-md text-xs text-[#2648C7]">
            <span className="font-semibold block mb-0.5">Runtime / Environment Differences</span>
            <span>{Array.isArray(record.runtime_differences) ? record.runtime_differences.join(' · ') : record.runtime_differences}</span>
          </div>
        )}

        {/* Output logs */}
        <BoundedOutputView label="Standard Output (stdout)" content={record?.stdout_excerpt} />
        <BoundedOutputView label="Standard Error (stderr)" content={record?.stderr_excerpt} />

        {/* Provenance note */}
        <div className="mt-auto pt-3 border-t border-[#E1E6EE] flex items-center justify-between text-[11px] text-[#718096]">
          <span>Evidence Provenance</span>
          <StatusBadge variant={status === 'NOT_RUN' ? 'neutral' : 'success'} size="sm">
            {record?.provenance || (status === 'NOT_RUN' ? 'NOT_VERIFIED' : 'EXECUTION_RESULT')}
          </StatusBadge>
        </div>
      </div>
    </div>
  );
}

// ─── Human Approval Dialog ───────────────────────────────────────────────────

interface ApprovalModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  repositoryValue?: string;
  dependencyName?: string;
  baselineProfileId: string;
  replacementProfileId?: string;
  timeoutSeconds: number;
  allowNetwork: boolean;
  isSubmitting: boolean;
}

function ApprovalModal({
  open,
  onClose,
  onConfirm,
  repositoryValue,
  dependencyName,
  baselineProfileId,
  replacementProfileId,
  timeoutSeconds,
  allowNetwork,
  isSubmitting,
}: ApprovalModalProps) {
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (open) setConfirmed(false);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs transition-opacity duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-title"
    >
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full border border-[#E1E6EE] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-5 py-4 border-b border-[#E1E6EE] flex items-center gap-3 bg-[#FFF5DE]">
          <div className="w-8 h-8 rounded-full bg-[#FDE4A4] flex items-center justify-center shrink-0">
            <AlertTriangle className="w-4 h-4 text-[#925C08]" />
          </div>
          <div>
            <h2 id="approval-title" className="text-sm font-semibold text-[#172033]">
              Confirm Repository Code Execution
            </h2>
            <p className="text-xs text-[#925C08]">Human approval required before running test profiles</p>
          </div>
        </div>

        {/* Content */}
        <div className="p-5 flex flex-col gap-4 text-xs text-[#526176]">
          <p className="leading-relaxed">
            ExitLens executes test profiles strictly in a disposable workspace with isolated argument lists. Because running repository test suites executes code authored in the repository, explicit confirmation is mandatory.
          </p>

          <div className="bg-[#FAFBFC] border border-[#E1E6EE] rounded-lg p-3 flex flex-col gap-2">
            <div className="flex justify-between py-1 border-b border-[#E1E6EE]">
              <span className="text-[#718096]">Target Repository:</span>
              <span className="font-mono text-[#172033] font-medium truncate max-w-64" title={repositoryValue}>
                {repositoryValue || '—'}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#E1E6EE]">
              <span className="text-[#718096]">Selected Dependency:</span>
              <span className="font-mono text-[#172033] font-medium">{dependencyName || '—'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#E1E6EE]">
              <span className="text-[#718096]">Baseline Profile:</span>
              <span className="font-mono text-[#172033]">{baselineProfileId}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#E1E6EE]">
              <span className="text-[#718096]">Replacement Profile:</span>
              <span className="font-mono text-[#172033]">{replacementProfileId || 'None (baseline only)'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#E1E6EE]">
              <span className="text-[#718096]">Execution Timeout:</span>
              <span className="font-semibold text-[#172033]">{timeoutSeconds} seconds</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-[#718096]">Network Policy:</span>
              <span className="font-medium text-[#172033]">
                {allowNetwork ? 'Allowed (Explicitly enabled)' : 'Disabled (Default Isolated Sandbox)'}
              </span>
            </div>
          </div>

          <label className="flex items-start gap-2.5 p-3 rounded-lg border border-[#E1E6EE] bg-[#F5F7FA] hover:bg-[#EEF1F5] cursor-pointer transition-colors">
            <input
              type="checkbox"
              id="confirm-code-execution"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-[#CCD5E2] text-[#315BE8] focus:ring-[#315BE8] cursor-pointer"
            />
            <span className="text-xs text-[#172033] leading-relaxed">
              I acknowledge and approve executing repository test code in a disposable workspace under the stated parameters.
            </span>
          </label>
        </div>

        {/* Footer */}
        <div className="px-5 py-3.5 bg-[#F5F7FA] border-t border-[#E1E6EE] flex items-center justify-end gap-2.5">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onConfirm}
            disabled={!confirmed || isSubmitting}
            icon={isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          >
            {isSubmitting ? 'Submitting...' : 'Confirm & Execute Verification'}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Main VerificationPage Component ─────────────────────────────────────────

export function VerificationPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { activeAnalysis, selectedDependencyIds, setSelectedDependencyIds } = useAnalysisContext();

  const analysisId = activeAnalysis?.analysis_id ?? null;

  // Retrieve inventory list to support dependency selection
  const { state: listState } = useDependencyList(analysisId);
  const dependencies = listState.status === 'loaded' ? listState.items : [];

  // Determine active selected dependency ID
  const paramDepId = searchParams.get('dep') || searchParams.get('dependency_id');
  const [activeDepId, setActiveDepId] = useState<string | null>(() => {
    if (paramDepId) return paramDepId;
    if (selectedDependencyIds.length > 0) return selectedDependencyIds[0];
    return null;
  });

  // Keep activeDepId in sync if context or URL param changes
  useEffect(() => {
    if (paramDepId) {
      setActiveDepId(paramDepId);
    } else if (selectedDependencyIds.length > 0 && !activeDepId) {
      setActiveDepId(selectedDependencyIds[0]);
    } else if (!activeDepId && dependencies.length > 0) {
      setActiveDepId(dependencies[0].dependency_id);
    }
  }, [paramDepId, selectedDependencyIds, dependencies, activeDepId]);

  // Load detail for selected dependency
  const detailState = useDependencyDetail(analysisId, activeDepId);

  // Verification configuration state
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(DEFAULT_TIMEOUT_SECONDS);
  const [allowNetwork, setAllowNetwork] = useState<boolean>(false);

  const [availableProfiles, setAvailableProfiles] = useState<TestProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('pytest-default');

  useEffect(() => {
    if (!analysisId) return;
    let isMounted = true;
    getTestProfiles(analysisId)
      .then((profiles) => {
        if (!isMounted) return;
        setAvailableProfiles(profiles);
        const detected = profiles.find((p) => p.is_detected);
        if (detected) {
          setSelectedProfileId(detected.profile_id);
        } else if (profiles.length > 0) {
          setSelectedProfileId(profiles[0].profile_id);
        }
      })
      .catch((err) => {
        console.warn('Could not fetch test profiles:', err);
      });
    return () => {
      isMounted = false;
    };
  }, [analysisId]);

  // Derive server-supplied profile IDs if present in existing detail, otherwise use selected or contract standard token
  const serverBaselineProfile = useMemo(() => {
    if (detailState.status === 'loaded' && detailState.detail.executed_test_results) {
      const match = detailState.detail.executed_test_results.find((r) => r.is_baseline && r.profile_id);
      if (match?.profile_id) return match.profile_id;
    }
    return null;
  }, [detailState]);

  const serverReplacementProfile = useMemo(() => {
    if (detailState.status === 'loaded' && detailState.detail.executed_test_results) {
      const match = detailState.detail.executed_test_results.find((r) => !r.is_baseline && r.profile_id);
      if (match?.profile_id) return match.profile_id;
    }
    return null;
  }, [detailState]);

  const baselineProfileId = availableProfiles.length > 0 ? selectedProfileId : (serverBaselineProfile || 'server-detected-profile-id');
  const replacementProfileId = availableProfiles.length > 0 ? selectedProfileId : (serverReplacementProfile || 'server-detected-profile-id');

  // Human approval modal state
  const [isApprovalOpen, setIsApprovalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [verificationError, setVerificationError] = useState<ApiClientError | null>(null);
  const [verificationResponse, setVerificationResponse] = useState<VerificationResponse | null>(null);

  // Active dependency item from list
  const activeDepItem = useMemo(() => {
    return dependencies.find((d) => d.dependency_id === activeDepId);
  }, [dependencies, activeDepId]);

  // Read existing execution results from detail if not yet run in session
  const existingBaseline = useMemo(() => {
    if (verificationResponse?.baseline_result) return verificationResponse.baseline_result;
    if (verificationResponse?.results) {
      return verificationResponse.results.find((r) => r.is_baseline);
    }
    if (detailState.status === 'loaded' && detailState.detail.executed_test_results) {
      const found = detailState.detail.executed_test_results.find((r) => r.is_baseline);
      if (found) {
        return {
          ...found,
          is_baseline: true,
        };
      }
    }
    return null;
  }, [verificationResponse, detailState]);

  const existingReplacement = useMemo(() => {
    if (verificationResponse?.replacement_result) return verificationResponse.replacement_result;
    if (verificationResponse?.results) {
      return verificationResponse.results.find((r) => !r.is_baseline);
    }
    if (detailState.status === 'loaded' && detailState.detail.executed_test_results) {
      const found = detailState.detail.executed_test_results.find((r) => !r.is_baseline);
      if (found) {
        return {
          ...found,
          is_baseline: false,
        };
      }
    }
    return null;
  }, [verificationResponse, detailState]);

  // Overall runner status
  const runnerStatus = useMemo(() => {
    if (isSubmitting) return 'Submitting';
    if (verificationResponse?.status === 'queued') return 'Queued';
    if (verificationResponse?.status === 'running') return 'Running';
    if (verificationResponse?.status) return verificationResponse.status;
    if (existingBaseline || existingReplacement) return 'Completed';
    return 'Runner Idle';
  }, [isSubmitting, verificationResponse, existingBaseline, existingReplacement]);

  // Handle verification submission
  const handleSubmitVerification = useCallback(async () => {
    if (!analysisId || !activeDepId) return;

    setIsSubmitting(true);
    setVerificationError(null);

    const payload: VerificationRequest = {
      dependency_ids: [activeDepId],
      baseline_profile_id: baselineProfileId || 'server-detected-profile-id',
      replacement_profile_id: replacementProfileId || 'server-detected-profile-id',
      confirm_repository_code_execution: true,
      allow_network: allowNetwork,
      timeout_seconds: timeoutSeconds,
    };

    try {
      const res = await postVerification(analysisId, payload);
      setVerificationResponse(res);
      setIsApprovalOpen(false);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setVerificationError(err);
      } else {
        setVerificationError(
          new ApiClientError('Verification request failed. Backend may be offline or unavailable.', 500)
        );
      }
      setIsApprovalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  }, [analysisId, activeDepId, baselineProfileId, replacementProfileId, allowNetwork, timeoutSeconds]);

  // ─── Guard 1: No active analysis ───────────────────────────────────────────
  if (!activeAnalysis) {
    return (
      <div className="flex flex-col gap-6 animate-in fade-in duration-200">
        <PageHeader
          title="Verification Workbench"
          description="Execute allow-listed test profiles in disposable copies to compare baseline and replacement outcomes before migration."
          badge={<StatusBadge variant="neutral" size="sm">No Active Run</StatusBadge>}
          breadcrumbs={[{ label: 'Workbench' }, { label: 'Verification' }]}
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/workspace')}
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
            >
              Back to Workspace
            </Button>
          }
        />
        <Panel
          title="Verification Suite Offline"
          subtitle="A repository analysis must be initiated before verification trials can be configured or executed."
        >
          <EmptyState
            icon={<ShieldCheck className="w-6 h-6" />}
            title="No Active Repository Analysis"
            description="Verification profiles, baseline runs, and counterfactual trials become available once a repository is analyzed."
            action={
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/workspace')}
                icon={<ArrowLeft className="w-3.5 h-3.5" />}
              >
                Configure Repository Scan
              </Button>
            }
          />
        </Panel>
      </div>
    );
  }

  // ─── Guard 2: No dependency selected ───────────────────────────────────────
  if (!activeDepId && dependencies.length === 0 && listState.status === 'loaded') {
    return (
      <div className="flex flex-col gap-6 animate-in fade-in duration-200">
        <PageHeader
          title="Verification Workbench"
          description="Compare baseline and feasible replacement checks to understand what has actually been tested and which compatibility questions remain unresolved."
          badge={<StatusBadge variant="neutral" size="sm">No Dependency Selected</StatusBadge>}
          breadcrumbs={[{ label: 'Workbench' }, { label: 'Analysis', href: '/analysis' }, { label: 'Verification' }]}
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/analysis')}
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
            >
              Back to Inventory
            </Button>
          }
        />
        <Panel
          title="Candidate Selection Required"
          subtitle="Select a dependency candidate from the inventory to configure and run verification trials."
        >
          <EmptyState
            icon={<Package className="w-6 h-6" />}
            title="No Dependencies Available for Verification"
            description="The current scan did not yield flagged dependencies or candidates for verification testing."
            action={
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/analysis')}
                icon={<ArrowLeft className="w-3.5 h-3.5" />}
              >
                Open Dependency Inventory
              </Button>
            }
          />
        </Panel>
      </div>
    );
  }

  const detail = detailState.status === 'loaded' ? detailState.detail : null;
  const replacement = detail?.proposed_replacement;

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <PageHeader
        title="Verification Workbench"
        description="Compare baseline and feasible replacement checks to understand what has actually been tested and which compatibility questions remain unresolved."
        badge={
          <StatusBadge
            variant={
              runnerStatus === 'Completed' || runnerStatus === 'PASSED'
                ? 'success'
                : runnerStatus === 'Running' || runnerStatus === 'Submitting'
                ? 'info'
                : runnerStatus === 'FAILED'
                ? 'failure'
                : 'neutral'
            }
            size="sm"
            icon={<Terminal className="w-3 h-3" />}
          >
            {runnerStatus}
          </StatusBadge>
        }
        breadcrumbs={[
          { label: 'Workbench' },
          { label: 'Analysis', href: '/analysis' },
          { label: 'Verification' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/analysis')}
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
            >
              Back to Inventory
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/capsule${activeDepId ? `?dep=${activeDepId}` : ''}`)}
              icon={<PackageCheck className="w-3.5 h-3.5" />}
            >
              View Capsule
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/workspace')}
            >
              Workspace
            </Button>
          </div>
        }
      />

      {/* Execution Safety Notice Banner */}
      <div className="p-4 bg-[#FFF5DE] border border-[#FDE4A4] rounded-lg flex items-start gap-3 text-xs text-[#925C08] shadow-xs">
        <AlertTriangle className="w-5 h-5 text-[#925C08] shrink-0 mt-0.5" />
        <div className="flex flex-col gap-1 flex-1">
          <span className="font-semibold text-[#172033]">Safety Boundary & Code Execution Notice</span>
          <span className="leading-relaxed">
            ExitLens executes repository test code only after explicit human confirmation. All verification trials run within disposable workspaces with isolated argument lists, bounded runtimes, and disabled network access. Original repository files are never modified.
          </span>
        </div>
      </div>

      {/* Backend / Verification Error State */}
      {verificationError && (
        <div className="p-4 bg-[#FEF0F0] border border-[#FECDCA] rounded-lg flex items-start justify-between gap-3 text-xs text-[#B42318] shadow-xs">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block mb-0.5">
                Verification Request Failed [{verificationError.code}]
              </span>
              <p className="leading-relaxed">{verificationError.message}</p>
              {verificationError.details && (
                <pre className="mt-1 font-mono text-[11px] bg-white/50 p-2 rounded">
                  {JSON.stringify(verificationError.details, null, 2)}
                </pre>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setVerificationError(null)}
            icon={<RotateCcw className="w-3.5 h-3.5" />}
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Workbench Configuration & Target Strip */}
      <Panel
        title="Verification Target & Safety Configuration"
        subtitle="Select the candidate dependency, configure execution parameters, and confirm safety boundaries."
      >
        <div className="flex flex-col gap-5">
          {/* Target Selector & Info Card */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Dependency Selector */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="dependency-select" className="text-xs font-semibold text-[#172033]">
                Selected Dependency Candidate
              </label>
              {dependencies.length > 0 ? (
                <select
                  id="dependency-select"
                  value={activeDepId || ''}
                  onChange={(e) => {
                    setActiveDepId(e.target.value);
                    setSelectedDependencyIds([e.target.value]);
                  }}
                  className="h-9 text-xs border border-[#E1E6EE] rounded-md px-2.5 bg-white text-[#172033] focus:outline-none focus:ring-1 focus:ring-[#315BE8] cursor-pointer"
                >
                  {dependencies.map((d) => (
                    <option key={d.dependency_id} value={d.dependency_id}>
                      {d.name} ({d.declared_version || 'any'}) — {d.highest_severity?.toUpperCase() || 'INFO'}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="h-9 px-3 text-xs border border-[#E1E6EE] rounded-md bg-[#FAFBFC] flex items-center text-[#718096]">
                  {activeDepItem?.name || activeDepId || 'No selection'}
                </div>
              )}
              <span className="text-[11px] text-[#718096]">
                Repository target: <span className="font-mono text-[#526176]">{activeAnalysis.repository?.value || 'local'}</span>
              </span>
            </div>

            {/* Proposed Replacement Card */}
            <div className="flex flex-col gap-1 lg:col-span-2 p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md text-xs">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 text-[#172033] font-semibold">
                  <Lightbulb className="w-3.5 h-3.5 text-[#315BE8]" />
                  <span>Proposed Replacement (Gemma 4 Recommendation)</span>
                </div>
                {replacement && (
                  <StatusBadge variant="warning" size="sm">
                    AI_RECOMMENDATION
                  </StatusBadge>
                )}
              </div>
              {replacement ? (
                <div className="mt-1 flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[#172033]">
                      {replacement.candidate_distribution || 'No candidate distribution'}
                    </span>
                    {replacement.candidate_specifier && (
                      <span className="font-mono text-[#526176]">{replacement.candidate_specifier}</span>
                    )}
                  </div>
                  {replacement.rationale && (
                    <p className="text-[#526176] leading-relaxed line-clamp-2">{replacement.rationale}</p>
                  )}
                  {replacement.limitations && (
                    <p className="text-[11px] text-[#925C08] italic">{replacement.limitations}</p>
                  )}
                </div>
              ) : (
                <p className="text-[#718096] italic mt-1">
                  No replacement candidate available for this package. Verification will evaluate baseline tests only.
                </p>
              )}
            </div>
          </div>

          {/* Test Profile & Safety Controls */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 border-t border-[#E1E6EE]">
            {/* Permitted Profile Info */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-[#172033] flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-[#526176]" />
                Permitted Test Profiles
              </label>
              <div className="p-2.5 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md text-xs flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[#718096]">Profile:</span>
                  {availableProfiles.length > 0 ? (
                    <select
                      id="profile-select"
                      value={selectedProfileId}
                      onChange={(e) => setSelectedProfileId(e.target.value)}
                      className="font-mono text-xs text-[#172033] bg-white border border-[#E1E6EE] rounded px-2 py-1 flex-1 max-w-[200px]"
                    >
                      {availableProfiles.map((p) => (
                        <option key={p.profile_id} value={p.profile_id}>
                          {p.display_name} {p.is_detected ? '★ (Detected)' : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="font-mono text-[#172033] font-medium">{baselineProfileId}</span>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#718096]">Profile ID:</span>
                  <span className="font-mono text-[11px] text-[#526176]">{baselineProfileId}</span>
                </div>
              </div>
              <span className="text-[11px] text-[#718096] leading-relaxed">
                Allow-listed test profiles detected from repository. Arbitrary shell commands are rejected by design.
              </span>
            </div>

            {/* Timeout Configuration */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="timeout-input" className="text-xs font-semibold text-[#172033] flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-[#526176]" />
                Timeout Limit ({timeoutSeconds}s)
              </label>
              <div className="flex items-center gap-2">
                <input
                  id="timeout-input"
                  type="range"
                  min={MIN_TIMEOUT_SECONDS}
                  max={MAX_TIMEOUT_SECONDS}
                  step={5}
                  value={timeoutSeconds}
                  onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
                  className="flex-1 accent-[#315BE8] cursor-pointer"
                />
                <span className="font-mono text-xs font-semibold text-[#172033] w-12 text-right">
                  {timeoutSeconds}s
                </span>
              </div>
              <span className="text-[11px] text-[#718096]">
                Supported bounds: {MIN_TIMEOUT_SECONDS}s to {MAX_TIMEOUT_SECONDS}s (default {DEFAULT_TIMEOUT_SECONDS}s).
              </span>
            </div>

            {/* Network Policy & Trigger Button */}
            <div className="flex flex-col gap-2 justify-between">
              <div>
                <label className="text-xs font-semibold text-[#172033] flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-[#526176]" />
                  Network Policy
                </label>
                <div className="mt-1 flex items-center gap-2">
                  <StatusBadge variant={allowNetwork ? 'warning' : 'neutral'} size="sm">
                    {allowNetwork ? 'Network Allowed' : 'Network Disabled (Isolated)'}
                  </StatusBadge>
                  <label className="text-[11px] text-[#526176] flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allowNetwork}
                      onChange={(e) => setAllowNetwork(e.target.checked)}
                      className="rounded border-[#CCD5E2] text-[#315BE8] focus:ring-[#315BE8]"
                    />
                    Enable network
                  </label>
                </div>
              </div>

              <Button
                variant="primary"
                size="md"
                onClick={() => setIsApprovalOpen(true)}
                disabled={isSubmitting || !activeDepId}
                icon={isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                className="w-full justify-center"
              >
                {isSubmitting ? 'Submitting Verification...' : 'Review & Run Verification'}
              </Button>
            </div>
          </div>
        </div>
      </Panel>

      {/* Verification Results Panel — Side-by-Side Comparison */}
      <Panel
        title="Test Execution & Comparison Suite"
        subtitle="Side-by-side comparison of baseline test runs versus candidate replacement trials."
        actions={
          <StatusBadge
            variant={
              runnerStatus === 'Completed' || runnerStatus === 'PASSED'
                ? 'success'
                : runnerStatus === 'Running' || runnerStatus === 'Submitting'
                ? 'info'
                : runnerStatus === 'FAILED'
                ? 'failure'
                : 'neutral'
            }
            size="sm"
            icon={<Terminal className="w-3 h-3" />}
          >
            {runnerStatus}
          </StatusBadge>
        }
      >
        <div className="flex flex-col gap-6">
          {/* Important distinction notice */}
          <div className="p-3 bg-[#EEF3FF] border border-[#C6D8FF] rounded-lg text-xs text-[#2648C7] flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-[#315BE8] shrink-0 mt-0.5" />
            <div className="leading-relaxed">
              <strong>Distinction Notice:</strong> A recommended test or AI proposal is not proof of compatibility. The replacement candidate is tested only when an allow-listed test profile executes in a disposable copy. If only the baseline runs, the replacement is never marked as passed.
            </div>
          </div>

          {/* Side-by-Side Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Baseline Column */}
            <ExecutionCard
              title="Baseline Test Suite"
              subtitle="Original repository test state before dependency modification"
              isBaseline={true}
              record={existingBaseline}
              fallbackStatus="NOT_RUN"
              fallbackReason="Baseline test execution has not yet been executed for this candidate."
              profileId={baselineProfileId}
            />

            {/* Replacement Column */}
            <ExecutionCard
              title="Candidate Replacement Trial"
              subtitle="Isolated trial with proposed replacement in disposable copy"
              isBaseline={false}
              record={existingReplacement}
              fallbackStatus="NOT_RUN"
              fallbackReason={
                replacement
                  ? 'Replacement verification trial has not yet been triggered.'
                  : 'No candidate replacement identified for this dependency; replacement trial omitted.'
              }
              profileId={replacementProfileId}
            />
          </div>

          {/* Suggested Tests Section from Gemma 4 (Unexecuted Proposals) */}
          {detail?.suggested_tests && detail.suggested_tests.length > 0 && (
            <div className="border border-[#E1E6EE] rounded-lg p-4 bg-[#FAFBFC]">
              <div className="flex items-center justify-between pb-2 border-b border-[#E1E6EE] mb-3">
                <div className="flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-[#315BE8]" />
                  <h3 className="text-xs font-semibold text-[#172033] uppercase tracking-wider">
                    Suggested Tests (Gemma 4 Proposals — Unexecuted Recommendations)
                  </h3>
                </div>
                <StatusBadge variant="warning" size="sm">
                  AI_RECOMMENDATION
                </StatusBadge>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                {detail.suggested_tests.map((t, idx) => (
                  <div key={idx} className="p-3 bg-white border border-[#E1E6EE] rounded-md flex flex-col gap-1.5">
                    <p className="font-medium text-[#172033]">{t.description}</p>
                    {t.test_type && (
                      <span className="text-[11px] font-mono text-[#718096]">Type: {t.test_type}</span>
                    )}
                    {t.code_example && (
                      <pre className="text-[11px] font-mono bg-[#F5F7FA] p-2 rounded border border-[#E1E6EE] overflow-x-auto">
                        {t.code_example}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Compatibility Gaps & Open Concerns */}
          {((detail?.compatibility_gaps && detail.compatibility_gaps.length > 0) ||
            (detail?.open_concerns_limitations && detail.open_concerns_limitations.length > 0)) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {detail.compatibility_gaps && detail.compatibility_gaps.length > 0 && (
                <div className="border border-[#E1E6EE] rounded-lg p-4 bg-white">
                  <h4 className="text-xs font-semibold text-[#172033] uppercase tracking-wider pb-2 border-b border-[#E1E6EE] mb-2">
                    Compatibility Gaps
                  </h4>
                  <div className="flex flex-col gap-2 text-xs">
                    {detail.compatibility_gaps.map((g, idx) => (
                      <div key={idx} className="p-2.5 bg-[#FFF5DE] border border-[#FDE4A4] rounded-md text-[#925C08]">
                        <p className="text-[#172033] font-medium">{g.description}</p>
                        {g.severity && (
                          <StatusBadge variant={severityVariant(g.severity)} size="sm" className="mt-1">
                            {g.severity.toUpperCase()}
                          </StatusBadge>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {detail.open_concerns_limitations && detail.open_concerns_limitations.length > 0 && (
                <div className="border border-[#E1E6EE] rounded-lg p-4 bg-white">
                  <h4 className="text-xs font-semibold text-[#172033] uppercase tracking-wider pb-2 border-b border-[#E1E6EE] mb-2">
                    Open Concerns & Limitations
                  </h4>
                  <ul className="flex flex-col gap-2 text-xs">
                    {detail.open_concerns_limitations.map((c, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-[#718096] shrink-0 mt-0.5">•</span>
                        <span className="text-[#526176] leading-relaxed">{c.description}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </Panel>

      {/* Human Approval Modal */}
      <ApprovalModal
        open={isApprovalOpen}
        onClose={() => setIsApprovalOpen(false)}
        onConfirm={handleSubmitVerification}
        repositoryValue={activeAnalysis.repository?.value}
        dependencyName={activeDepItem?.name || activeDepId || undefined}
        baselineProfileId={baselineProfileId}
        replacementProfileId={replacementProfileId}
        timeoutSeconds={timeoutSeconds}
        allowNetwork={allowNetwork}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
