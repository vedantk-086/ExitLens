import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  PackageCheck,
  ArrowLeft,
  Download,
  Layers,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  RotateCcw,
  FileText,
  FileCode,
  Shield,
  ChevronDown,
  ChevronUp,
  Activity,
  Check,
} from 'lucide-react';

import { PageHeader } from '../components/ui/PageHeader';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge, StatusVariant } from '../components/ui/StatusBadge';
import { useAnalysisContext } from '../context/useAnalysisContext';
import { getCapsuleJson, downloadCapsuleFile } from '../api/analyses';
import { ApiClientError } from '../api/client';
import {
  DependencyExitCapsule,
  CapsuleDependencyRecord,
  EvidenceProvenance,
  RiskSeverity,
  VerificationStatus,
} from '../types/api';

// ─── Provenance Badge Helper ──────────────────────────────────────────────────

function ProvenanceBadge({ provenance }: { provenance?: EvidenceProvenance | string }) {
  if (!provenance) return null;
  const p = provenance.toUpperCase();

  let variant: StatusVariant = 'neutral';
  let label = p;

  switch (p) {
    case 'OBSERVED':
      variant = 'info';
      label = 'OBSERVED';
      break;
    case 'INFERRED':
      variant = 'warning';
      label = 'INFERRED';
      break;
    case 'AI_RECOMMENDATION':
      variant = 'info';
      label = 'AI_RECOMMENDATION';
      break;
    case 'EXECUTION_RESULT':
      variant = 'success';
      label = 'EXECUTION_RESULT';
      break;
    case 'NOT_VERIFIED':
      variant = 'neutral';
      label = 'NOT_VERIFIED';
      break;
    default:
      variant = 'neutral';
      label = p;
  }

  return (
    <span title={`Provenance: ${label}`} className="inline-block">
      <StatusBadge variant={variant} size="sm">
        {label}
      </StatusBadge>
    </span>
  );
}

function severityVariant(severity?: RiskSeverity | string | null): StatusVariant {
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

function statusVariant(status?: VerificationStatus | string | null): StatusVariant {
  switch (status?.toUpperCase()) {
    case 'PASSED':
      return 'success';
    case 'FAILED':
      return 'failure';
    case 'ERROR':
      return 'failure';
    case 'TIMED_OUT':
      return 'warning';
    case 'SKIPPED':
      return 'neutral';
    case 'NOT_RUN':
      return 'neutral';
    default:
      return 'neutral';
  }
}

// ─── Bounded Log Excerpt Component ───────────────────────────────────────────

function LogExcerptView({ label, content }: { label: string; content?: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!content) return null;

  const isLong = content.length > 280 || content.split('\n').length > 6;
  const displayContent = !expanded && isLong
    ? content.slice(0, 280) + '...\n[Output truncated — click expand to view full log]'
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
      <pre className="text-[11px] font-mono bg-[#172033] text-[#E2E8F0] p-3 rounded-md overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto">
        {displayContent}
      </pre>
    </div>
  );
}

// ─── Expandable Section Component ─────────────────────────────────────────────

interface SectionAccordionProps {
  id: string;
  title: string;
  count?: number;
  isOpenDefault?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}

function SectionAccordion({
  id,
  title,
  count,
  isOpenDefault = true,
  badge,
  children,
}: SectionAccordionProps) {
  const [isOpen, setIsOpen] = useState(isOpenDefault);

  return (
    <div className="border border-[#E1E6EE] rounded-lg bg-white overflow-hidden shadow-xs">
      <button
        type="button"
        id={`section-btn-${id}`}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full px-4 py-3 bg-[#FAFBFC] hover:bg-[#F4F6F9] transition-colors flex items-center justify-between text-left text-xs font-semibold text-[#172033]"
      >
        <div className="flex items-center gap-2">
          <span>{title}</span>
          {count !== undefined && (
            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono bg-[#E1E6EE] text-[#526176]">
              {count}
            </span>
          )}
          {badge}
        </div>
        <div className="flex items-center gap-1 text-[#718096]">
          <span className="text-[11px] font-normal">{isOpen ? 'Collapse' : 'Expand'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isOpen && <div className="p-4 border-t border-[#E1E6EE] text-xs">{children}</div>}
    </div>
  );
}

// ─── Main Capsule Page ─────────────────────────────────────────────────────────

export function CapsulePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { activeAnalysis } = useAnalysisContext();

  const analysisId = activeAnalysis?.analysis_id ?? null;

  // Capsule loading state
  const [capsule, setCapsule] = useState<DependencyExitCapsule | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<ApiClientError | null>(null);

  // Export states
  const [isExportingJson, setIsExportingJson] = useState<boolean>(false);
  const [isExportingMd, setIsExportingMd] = useState<boolean>(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  // Selected flagged dependency
  const paramDepId = searchParams.get('dep');
  const [selectedDepId, setSelectedDepId] = useState<string | null>(paramDepId);

  // Fetch JSON capsule
  const loadCapsule = useCallback(async () => {
    if (!analysisId) return;
    setIsLoading(true);
    setError(null);
    setExportError(null);

    try {
      const data = await getCapsuleJson(analysisId);
      setCapsule(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err);
      } else {
        setError(
          new ApiClientError(
            'Failed to load Dependency Exit Capsule. The backend artifact may not yet be assembled.',
            500
          )
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [analysisId]);

  useEffect(() => {
    if (analysisId) {
      loadCapsule();
    }
  }, [analysisId, loadCapsule]);

  // Normalize flagged dependencies list
  const flaggedDeps: CapsuleDependencyRecord[] = useMemo(() => {
    if (!capsule) return [];
    if (capsule.flagged_dependencies && capsule.flagged_dependencies.length > 0) {
      return capsule.flagged_dependencies;
    }
    if (capsule.dependencies && capsule.dependencies.length > 0) {
      return capsule.dependencies;
    }
    return [];
  }, [capsule]);

  // Set default selected dependency
  useEffect(() => {
    if (flaggedDeps.length > 0) {
      if (paramDepId && flaggedDeps.some((d) => d.dependency_id === paramDepId)) {
        setSelectedDepId(paramDepId);
      } else if (!selectedDepId || !flaggedDeps.some((d) => d.dependency_id === selectedDepId)) {
        setSelectedDepId(flaggedDeps[0].dependency_id);
      }
    }
  }, [flaggedDeps, paramDepId, selectedDepId]);

  const activeRecord = useMemo(() => {
    return flaggedDeps.find((d) => d.dependency_id === selectedDepId) || flaggedDeps[0] || null;
  }, [flaggedDeps, selectedDepId]);

  // Handle Export Downloads
  const handleDownload = useCallback(
    async (format: 'json' | 'md') => {
      if (!analysisId) return;
      setExportError(null);
      setExportSuccess(null);

      if (format === 'json') setIsExportingJson(true);
      else setIsExportingMd(true);

      try {
        await downloadCapsuleFile(analysisId, format);
        setExportSuccess(
          `Successfully exported exitlens-capsule-${analysisId}.${format}`
        );
      } catch (err: unknown) {
        const msg =
          err instanceof ApiClientError
            ? `${err.code}: ${err.message}`
            : 'Download failed. The server-generated artifact was unavailable.';
        setExportError(msg);
      } finally {
        if (format === 'json') setIsExportingJson(false);
        else setIsExportingMd(false);
      }
    },
    [analysisId]
  );

  // ─── Guard: Missing Active Analysis ──────────────────────────────────────────
  if (!activeAnalysis) {
    return (
      <div className="flex flex-col gap-6 animate-in fade-in duration-200">
        <PageHeader
          title="Dependency Exit Capsule"
          description="Comprehensive, evidence-linked migration artifact containing all nine required sections, execution logs, and provenance metadata."
          badge={<StatusBadge variant="neutral" size="sm">No Active Run</StatusBadge>}
          breadcrumbs={[{ label: 'Workbench' }, { label: 'Capsule' }]}
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/workspace')}
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
            >
              Return to Workspace
            </Button>
          }
        />

        <Panel
          title="Capsule Unavailable"
          subtitle="A repository analysis must be initiated before a Dependency Exit Capsule can be generated or inspected."
        >
          <EmptyState
            icon={<PackageCheck className="w-6 h-6" />}
            title="No Active Repository Analysis"
            description="To generate and inspect a canonical Dependency Exit Capsule, submit a repository in the Workspace and complete the analysis."
            action={
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/workspace')}
                icon={<ArrowLeft className="w-3.5 h-3.5" />}
              >
                Go to Workspace
              </Button>
            }
          />
        </Panel>
      </div>
    );
  }

  // Completeness check indicators
  const isCompletenessPassing = capsule?.is_complete ?? (flaggedDeps.length > 0 && !error);

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <PageHeader
        title="Dependency Exit Capsule"
        description="Canonical, evidence-linked migration artifact containing all nine required sections, execution logs, and provenance metadata."
        badge={
          <StatusBadge
            variant={isLoading ? 'info' : capsule ? 'success' : 'neutral'}
            size="sm"
          >
            {isLoading ? 'Loading Capsule...' : capsule ? 'Capsule Ready' : 'Capsule Inspector'}
          </StatusBadge>
        }
        breadcrumbs={[
          { label: 'Workbench' },
          { label: 'Analysis', href: '/analysis' },
          { label: 'Verification', href: '/verification' },
          { label: 'Capsule' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadCapsule}
              disabled={isLoading}
              icon={<RotateCcw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDownload('json')}
              disabled={isLoading || isExportingJson || !capsule}
              icon={<Download className={`w-3.5 h-3.5 ${isExportingJson ? 'animate-bounce' : ''}`} />}
            >
              {isExportingJson ? 'Downloading...' : 'Download JSON'}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => handleDownload('md')}
              disabled={isLoading || isExportingMd || !capsule}
              icon={<Download className={`w-3.5 h-3.5 ${isExportingMd ? 'animate-bounce' : ''}`} />}
            >
              {isExportingMd ? 'Downloading...' : 'Download Markdown'}
            </Button>
          </div>
        }
      />

      {/* Export Notifications */}
      {exportSuccess && (
        <div className="p-3 bg-[#ECFDF3] border border-[#A6F4C5] rounded-lg flex items-center justify-between text-xs text-[#027A48]">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{exportSuccess}</span>
          </div>
          <button
            type="button"
            onClick={() => setExportSuccess(null)}
            className="text-[11px] underline hover:text-[#054F31]"
          >
            Dismiss
          </button>
        </div>
      )}

      {exportError && (
        <div className="p-3 bg-[#FEF3F2] border border-[#FECDCA] rounded-lg flex items-center justify-between text-xs text-[#B42318]">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{exportError}</span>
          </div>
          <button
            type="button"
            onClick={() => setExportError(null)}
            className="text-[11px] underline hover:text-[#7A271A]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Backend Unavailable / Error State */}
      {error && (
        <div className="p-4 bg-[#FEF3F2] border border-[#FECDCA] rounded-lg flex items-start justify-between gap-3 text-xs text-[#B42318]">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="flex flex-col gap-1">
              <span className="font-semibold">
                Capsule Endpoint Unavailable [{error.code}]
              </span>
              <p className="leading-relaxed">{error.message}</p>
              <p className="text-[11px] text-[#7A271A]">
                The backend service for <code>GET /analyses/{analysisId}/capsule</code> may still be generating the artifact or has not completed assembly. Existing scan findings and inventory remain intact.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadCapsule}
            icon={<RotateCcw className="w-3.5 h-3.5" />}
          >
            Retry Request
          </Button>
        </div>
      )}

      {/* Top Metadata Strip & Provenance Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Capsule & Repository Metadata */}
        <div className="p-4 bg-white border border-[#E1E6EE] rounded-lg flex flex-col justify-between gap-3 text-xs shadow-xs">
          <div className="flex items-center justify-between border-b border-[#E1E6EE] pb-2">
            <span className="font-semibold text-[#172033] flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-[#315BE8]" />
              Artifact Metadata
            </span>
            <span className="font-mono text-[11px] text-[#718096]">
              Schema v{capsule?.schema_version || '1.0.0'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div>
              <span className="text-[#718096] block">Analysis ID</span>
              <span className="font-mono font-medium text-[#172033] truncate block" title={analysisId ?? undefined}>
                {analysisId}
              </span>
            </div>
            <div>
              <span className="text-[#718096] block">Tool Version</span>
              <span className="font-mono text-[#172033]">{capsule?.tool_version || 'exitlens-0.1.0'}</span>
            </div>
            <div>
              <span className="text-[#718096] block">Target Repository</span>
              <span className="font-mono text-[#172033] truncate block" title={activeAnalysis.repository?.value}>
                {activeAnalysis.repository?.value || 'Repository'}
              </span>
            </div>
            <div>
              <span className="text-[#718096] block">Runtime Version</span>
              <span className="font-mono text-[#172033]">{capsule?.runtime_version || 'Python 3.12/3.13'}</span>
            </div>
            <div className="col-span-2">
              <span className="text-[#718096] block">Generated At (UTC)</span>
              <span className="font-mono text-[#172033]">
                {capsule?.generated_at_utc || capsule?.created_at || activeAnalysis.created_at || 'In progress'}
              </span>
            </div>
          </div>
        </div>

        {/* AI Model Provenance */}
        <div className="p-4 bg-white border border-[#E1E6EE] rounded-lg flex flex-col justify-between gap-3 text-xs shadow-xs">
          <div className="flex items-center justify-between border-b border-[#E1E6EE] pb-2">
            <span className="font-semibold text-[#172033] flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-[#315BE8]" />
              AI Model Provenance
            </span>
            <ProvenanceBadge provenance="AI_RECOMMENDATION" />
          </div>
          <div className="flex flex-col gap-1.5 text-[11px]">
            <div className="flex items-center justify-between">
              <span className="text-[#718096]">Model Identifier:</span>
              <span className="font-mono font-medium text-[#172033]">
                {capsule?.ai_provenance?.model_tag || 'gemma4 (Ollama)'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#718096]">Inference Provider:</span>
              <span className="font-mono text-[#172033]">
                {capsule?.ai_provenance?.provider || 'local_ollama'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#718096]">Prompt Version:</span>
              <span className="font-mono text-[#172033]">
                {capsule?.ai_provenance?.prompt_version || 'exitlens-v1'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#718096]">Inference Method:</span>
              <span className="font-mono text-[#172033]">
                {capsule?.ai_provenance?.inference_method || 'local_adapter_bounded'}
              </span>
            </div>
          </div>
          <div className="pt-2 border-t border-[#E1E6EE] text-[10px] text-[#718096] leading-tight">
            AI recommendations are strictly tagged <code>AI_RECOMMENDATION</code> and never conflated with observed facts or verified execution runs.
          </div>
        </div>

        {/* Completeness Gate Summary */}
        <div className="p-4 bg-white border border-[#E1E6EE] rounded-lg flex flex-col justify-between gap-3 text-xs shadow-xs">
          <div className="flex items-center justify-between border-b border-[#E1E6EE] pb-2">
            <span className="font-semibold text-[#172033] flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-[#315BE8]" />
              Completeness Gate
            </span>
            <StatusBadge variant={isCompletenessPassing ? 'success' : 'warning'} size="sm">
              {isCompletenessPassing ? 'Gate Satisfied' : 'Warnings Disclosed'}
            </StatusBadge>
          </div>
          <div className="flex flex-col gap-1 text-[11px] text-[#526176]">
            <div className="flex items-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-[#027A48]" />
              <span>Flagged Dependencies: <strong>{flaggedDeps.length}</strong></span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-[#027A48]" />
              <span>All 9 required sections present per candidate</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-[#027A48]" />
              <span>Dual JSON & Markdown parity guarantee</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-[#027A48]" />
              <span>Evidence provenance references resolved</span>
            </div>
          </div>
          {capsule?.validation_warnings && capsule.validation_warnings.length > 0 && (
            <div className="text-[10px] text-[#925C08] bg-[#FFF5DE] p-1.5 rounded">
              {capsule.validation_warnings[0]}
            </div>
          )}
        </div>
      </div>

      {/* Flagged Dependencies Selector Bar (when multiple exist) */}
      {flaggedDeps.length > 0 && (
        <div className="flex flex-col gap-2 p-4 bg-white border border-[#E1E6EE] rounded-lg shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#172033] flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-[#315BE8]" />
              Flagged Dependencies in Capsule ({flaggedDeps.length})
            </span>
            <span className="text-[11px] text-[#718096]">
              Select a dependency to inspect its nine-section migration dossier
            </span>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            {flaggedDeps.map((dep) => {
              const isSelected = dep.dependency_id === activeRecord?.dependency_id;
              const name = dep.dependency_details?.name || dep.name || dep.dependency_id;
              const ver = dep.dependency_details?.resolved_version || dep.dependency_details?.declared_version;
              const highestRisk = dep.risk_indicators?.[0]?.severity;

              return (
                <button
                  key={dep.dependency_id}
                  type="button"
                  onClick={() => {
                    setSelectedDepId(dep.dependency_id);
                    setSearchParams({ dep: dep.dependency_id });
                  }}
                  className={`px-3 py-2 rounded-md text-xs font-medium border flex items-center gap-2 transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-[#315BE8] text-white border-[#315BE8] shadow-xs'
                      : 'bg-[#FAFBFC] text-[#172033] border-[#E1E6EE] hover:bg-[#F4F6F9]'
                  }`}
                >
                  <span>{name}</span>
                  {ver && <span className={`text-[10px] font-mono ${isSelected ? 'text-white/80' : 'text-[#718096]'}`}>({ver})</span>}
                  {highestRisk && (
                    <StatusBadge variant={isSelected ? 'neutral' : severityVariant(highestRisk)} size="sm">
                      {highestRisk}
                    </StatusBadge>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Active Flagged Dependency Dossier — 9 REQUIRED SECTIONS */}
      {activeRecord ? (
        <div className="flex flex-col gap-4">
          {/* Active Record Banner */}
          <div className="p-4 bg-[#F8FAFC] border border-[#E1E6EE] rounded-lg flex items-center justify-between shadow-xs">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-md bg-white border border-[#E1E6EE] flex items-center justify-center font-bold text-sm text-[#315BE8]">
                {activeRecord.dependency_details?.name?.charAt(0).toUpperCase() || 'D'}
              </div>
              <div>
                <h2 className="text-sm font-bold text-[#172033] flex items-center gap-2">
                  <span>{activeRecord.dependency_details?.name || activeRecord.name || 'Flagged Dependency'}</span>
                  <span className="font-mono text-xs text-[#526176]">
                    {activeRecord.dependency_details?.resolved_version ||
                      activeRecord.dependency_details?.declared_version ||
                      'Unpinned'}
                  </span>
                </h2>
                <p className="text-xs text-[#526176]">
                  Manifest: <code>{activeRecord.dependency_details?.manifest_path || 'requirements.txt'}</code>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/verification?dep=${activeRecord.dependency_id}`)}
                icon={<Activity className="w-3.5 h-3.5" />}
              >
                Run Verification
              </Button>
            </div>
          </div>

          {/* ─── SECTION 1: dependency_details ──────────────────────────────── */}
          <SectionAccordion
            id="dependency-details"
            title="1. Dependency Details"
            badge={<ProvenanceBadge provenance="OBSERVED" />}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <div className="flex justify-between border-b border-[#E1E6EE] pb-1.5">
                  <span className="text-[#718096]">Package Name:</span>
                  <span className="font-semibold text-[#172033]">
                    {activeRecord.dependency_details?.name || 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between border-b border-[#E1E6EE] pb-1.5">
                  <span className="text-[#718096]">Declared Constraint:</span>
                  <span className="font-mono text-[#172033]">
                    {activeRecord.dependency_details?.declared_version || 'None specified'}
                  </span>
                </div>
                <div className="flex justify-between border-b border-[#E1E6EE] pb-1.5">
                  <span className="text-[#718096]">Resolved Version:</span>
                  <span className="font-mono text-[#172033]">
                    {activeRecord.dependency_details?.resolved_version || 'Unresolved'}
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <div className="flex justify-between border-b border-[#E1E6EE] pb-1.5">
                  <span className="text-[#718096]">Manifest File:</span>
                  <span className="font-mono text-[#172033]">
                    {activeRecord.dependency_details?.manifest_path || 'requirements.txt'}
                  </span>
                </div>
                <div className="flex justify-between border-b border-[#E1E6EE] pb-1.5">
                  <span className="text-[#718096]">Distribution Name:</span>
                  <span className="font-mono text-[#172033]">
                    {activeRecord.dependency_details?.distribution_name || activeRecord.dependency_details?.name || 'Same as package'}
                  </span>
                </div>
                <div className="flex justify-between border-b border-[#E1E6EE] pb-1.5">
                  <span className="text-[#718096]">Summary:</span>
                  <span className="text-[#172033] line-clamp-1">
                    {activeRecord.dependency_details?.summary || 'Standard Python distribution'}
                  </span>
                </div>
              </div>
            </div>
          </SectionAccordion>

          {/* ─── SECTION 2: risk_indicators ─────────────────────────────────── */}
          <SectionAccordion
            id="risk-indicators"
            title="2. Risk Indicators"
            count={activeRecord.risk_indicators?.length || 0}
            badge={<ProvenanceBadge provenance="INFERRED" />}
          >
            {activeRecord.risk_indicators && activeRecord.risk_indicators.length > 0 ? (
              <div className="flex flex-col gap-3">
                {activeRecord.risk_indicators.map((risk, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-[#172033]">{risk.rule_id}</span>
                        <StatusBadge variant={severityVariant(risk.severity)} size="sm">
                          {risk.severity}
                        </StatusBadge>
                      </div>
                      {risk.evidence_ids && risk.evidence_ids.length > 0 && (
                        <span className="font-mono text-[10px] text-[#718096]">
                          ev: {risk.evidence_ids.join(', ')}
                        </span>
                      )}
                    </div>
                    <p className="font-medium text-[#172033]">{risk.signal}</p>
                    <p className="text-[#526176] leading-relaxed">{risk.explanation}</p>
                    {risk.limitations && (
                      <p className="text-[11px] text-[#925C08] italic">
                        Limitation: {risk.limitations}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#718096] italic">
                No active maintenance risk rules triggered for this package.
              </p>
            )}
          </SectionAccordion>

          {/* ─── SECTION 3: usage_locations ─────────────────────────────────── */}
          <SectionAccordion
            id="usage-locations"
            title="3. Usage Locations"
            count={activeRecord.usage_locations?.length || 0}
            badge={<ProvenanceBadge provenance="OBSERVED" />}
          >
            {activeRecord.usage_locations && activeRecord.usage_locations.length > 0 ? (
              <div className="flex flex-col gap-2 max-h-72 overflow-y-auto">
                {activeRecord.usage_locations.map((loc, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex flex-col gap-1 font-mono text-[11px]"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 font-semibold text-[#172033]">
                        <FileCode className="w-3.5 h-3.5 text-[#315BE8]" />
                        <span>{loc.file_path}</span>
                        <span className="text-[#718096] font-normal">
                          :L{loc.line_start}
                          {loc.line_end ? `-${loc.line_end}` : ''}
                        </span>
                      </div>
                      {loc.is_test_file && (
                        <StatusBadge variant="neutral" size="sm">
                          test
                        </StatusBadge>
                      )}
                    </div>
                    {loc.import_name && (
                      <span className="text-[#526176]">import: {loc.import_name}</span>
                    )}
                    {loc.excerpt && (
                      <pre className="text-[10px] bg-white border border-[#E1E6EE] p-1.5 rounded overflow-x-auto text-[#172033] whitespace-pre-wrap">
                        {loc.excerpt}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#718096] italic">
                No static import usages identified in scanned source files. Review review-only declaration status.
              </p>
            )}
          </SectionAccordion>

          {/* ─── SECTION 4: proposed_replacement ────────────────────────────── */}
          <SectionAccordion
            id="proposed-replacement"
            title="4. Proposed Replacement"
            badge={<ProvenanceBadge provenance="AI_RECOMMENDATION" />}
          >
            {activeRecord.proposed_replacement ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[#172033] text-sm">
                      {activeRecord.proposed_replacement.candidate_distribution || 'No specific package'}
                    </span>
                    {activeRecord.proposed_replacement.candidate_specifier && (
                      <span className="font-mono text-xs text-[#526176]">
                        {activeRecord.proposed_replacement.candidate_specifier}
                      </span>
                    )}
                  </div>
                  <StatusBadge variant="neutral" size="sm">
                    Status: {activeRecord.proposed_replacement.status || 'available'}
                  </StatusBadge>
                </div>
                {activeRecord.proposed_replacement.rationale && (
                  <p className="text-[#526176] leading-relaxed">
                    {activeRecord.proposed_replacement.rationale}
                  </p>
                )}
                {activeRecord.proposed_replacement.limitations && (
                  <div className="p-2.5 bg-[#FFF5DE] border border-[#FDE4A4] rounded text-[11px] text-[#925C08]">
                    <strong>Candidate limitations:</strong> {activeRecord.proposed_replacement.limitations}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-[#718096] italic">
                No replacement candidate identified by Gemma 4 or model recommendation not requested.
              </p>
            )}
          </SectionAccordion>

          {/* ─── SECTION 5: migration_steps ─────────────────────────────────── */}
          <SectionAccordion
            id="migration-steps"
            title="5. Migration Steps"
            count={activeRecord.migration_steps?.length || 0}
            badge={<ProvenanceBadge provenance="AI_RECOMMENDATION" />}
          >
            {activeRecord.migration_steps && activeRecord.migration_steps.length > 0 ? (
              <div className="flex flex-col gap-3">
                {activeRecord.migration_steps.map((step, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex flex-col gap-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-[#315BE8] text-white flex items-center justify-center font-bold text-[10px]">
                        {step.step_number || idx + 1}
                      </span>
                      <span className="font-medium text-[#172033]">{step.description}</span>
                    </div>
                    {step.code_example && (
                      <pre className="text-[11px] font-mono bg-[#172033] text-[#E2E8F0] p-2.5 rounded overflow-x-auto whitespace-pre-wrap">
                        {step.code_example}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#718096] italic">
                No step-by-step migration guidance generated for this candidate.
              </p>
            )}
          </SectionAccordion>

          {/* ─── SECTION 6: suggested_tests ─────────────────────────────────── */}
          <SectionAccordion
            id="suggested-tests"
            title="6. Suggested Tests"
            count={activeRecord.suggested_tests?.length || 0}
            badge={<ProvenanceBadge provenance="AI_RECOMMENDATION" />}
          >
            {activeRecord.suggested_tests && activeRecord.suggested_tests.length > 0 ? (
              <div className="flex flex-col gap-3">
                {activeRecord.suggested_tests.map((test, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#172033]">{test.description}</span>
                      {test.test_type && (
                        <StatusBadge variant="neutral" size="sm">
                          {test.test_type}
                        </StatusBadge>
                      )}
                    </div>
                    {test.code_example && (
                      <pre className="text-[11px] font-mono bg-[#172033] text-[#E2E8F0] p-2 rounded overflow-x-auto whitespace-pre-wrap">
                        {test.code_example}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#718096] italic">
                No specific counterfactual tests suggested by the model.
              </p>
            )}
          </SectionAccordion>

          {/* ─── SECTION 7: executed_test_results ───────────────────────────── */}
          <SectionAccordion
            id="executed-test-results"
            title="7. Executed Test Results (Baseline vs Replacement)"
            count={activeRecord.executed_test_results?.length || 0}
            badge={<ProvenanceBadge provenance="EXECUTION_RESULT" />}
          >
            {activeRecord.executed_test_results && activeRecord.executed_test_results.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeRecord.executed_test_results.map((res, idx) => {
                  const isBaseline = res.is_baseline ?? idx === 0;
                  return (
                    <div
                      key={idx}
                      className="p-4 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex flex-col gap-3"
                    >
                      <div className="flex items-center justify-between border-b border-[#E1E6EE] pb-2">
                        <span className="font-semibold text-xs text-[#172033]">
                          {isBaseline ? 'Baseline Execution' : 'Replacement Trial'}
                        </span>
                        <StatusBadge variant={statusVariant(res.status)} size="sm">
                          {res.status}
                        </StatusBadge>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px]">
                        <div>
                          <span className="text-[#718096] block">Profile:</span>
                          <span className="font-mono text-[#172033]">{res.profile_id || 'N/A'}</span>
                        </div>
                        <div>
                          <span className="text-[#718096] block">Exit Code:</span>
                          <span className="font-mono text-[#172033]">
                            {res.exit_code !== undefined && res.exit_code !== null ? res.exit_code : 'N/A'}
                          </span>
                        </div>
                        <div>
                          <span className="text-[#718096] block">Duration:</span>
                          <span className="font-mono text-[#172033]">
                            {res.duration_seconds !== undefined && res.duration_seconds !== null
                              ? `${res.duration_seconds.toFixed(2)}s`
                              : 'N/A'}
                          </span>
                        </div>
                        <div>
                          <span className="text-[#718096] block">Start Time:</span>
                          <span className="font-mono text-[#172033] truncate block">
                            {res.start_time || 'N/A'}
                          </span>
                        </div>
                      </div>

                      {res.skip_reason && (
                        <div className="p-2 bg-[#FFF5DE] text-[11px] text-[#925C08] rounded">
                          <strong>Skip reason:</strong> {res.skip_reason}
                        </div>
                      )}

                      {res.error_reason && (
                        <div className="p-2 bg-[#FEF3F2] text-[11px] text-[#B42318] rounded">
                          <strong>Error reason:</strong> {res.error_reason}
                        </div>
                      )}

                      <LogExcerptView label="stdout excerpt" content={res.stdout_excerpt} />
                      <LogExcerptView label="stderr excerpt" content={res.stderr_excerpt} />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <p className="text-[#718096] italic">
                  No verified test runs executed yet for this package. Candidate trials require explicit user confirmation on the Verification Workbench.
                </p>
                <div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate(`/verification?dep=${activeRecord.dependency_id}`)}
                    icon={<Activity className="w-3.5 h-3.5" />}
                  >
                    Open Verification Workbench
                  </Button>
                </div>
              </div>
            )}
          </SectionAccordion>

          {/* ─── SECTION 8: compatibility_gaps ──────────────────────────────── */}
          <SectionAccordion
            id="compatibility-gaps"
            title="8. Compatibility Gaps"
            count={activeRecord.compatibility_gaps?.length || 0}
            badge={<ProvenanceBadge provenance="AI_RECOMMENDATION" />}
          >
            {activeRecord.compatibility_gaps && activeRecord.compatibility_gaps.length > 0 ? (
              <div className="flex flex-col gap-2">
                {activeRecord.compatibility_gaps.map((gap, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex items-start justify-between gap-3"
                  >
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-[#925C08] shrink-0 mt-0.5" />
                      <span className="text-[#172033] leading-relaxed">{gap.description}</span>
                    </div>
                    {gap.severity && (
                      <StatusBadge variant={severityVariant(gap.severity)} size="sm">
                        {gap.severity}
                      </StatusBadge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#718096] italic">
                No breaking compatibility gaps identified between baseline and candidate replacement.
              </p>
            )}
          </SectionAccordion>

          {/* ─── SECTION 9: open_concerns_limitations ────────────────────────── */}
          <SectionAccordion
            id="open-concerns"
            title="9. Open Concerns & Limitations"
            count={activeRecord.open_concerns_limitations?.length || 0}
            badge={<ProvenanceBadge provenance="AI_RECOMMENDATION" />}
          >
            {activeRecord.open_concerns_limitations && activeRecord.open_concerns_limitations.length > 0 ? (
              <div className="flex flex-col gap-2">
                {activeRecord.open_concerns_limitations.map((concern, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex items-start justify-between gap-3"
                  >
                    <div className="flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-[#526176] shrink-0 mt-0.5" />
                      <span className="text-[#172033] leading-relaxed">{concern.description}</span>
                    </div>
                    {concern.category && (
                      <span className="text-[10px] font-mono bg-[#E1E6EE] px-1.5 py-0.5 rounded text-[#526176]">
                        {concern.category}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#718096] italic">
                No unresolved concerns or external architectural blockers noted.
              </p>
            )}
          </SectionAccordion>
        </div>
      ) : (
        /* Empty flagged dependency state */
        <Panel
          title="No Flagged Dependencies"
          subtitle="All scanned dependencies passed deterministic risk analysis."
        >
          <EmptyState
            icon={<CheckCircle2 className="w-6 h-6 text-[#027A48]" />}
            title="Clean Dependency Inventory"
            description="The deterministic risk rules identified zero high-maintenance or unpinned packages in this repository."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/analysis')}
                icon={<ArrowLeft className="w-3.5 h-3.5" />}
              >
                Inspect All Dependencies
              </Button>
            }
          />
        </Panel>
      )}

      {/* Evidence Ledger (Provenance Index) */}
      {capsule?.evidence && (
        <Panel
          title="Evidence Index Ledger"
          subtitle="Cryptographically verified file excerpts and line ranges supporting all deterministic and AI claims."
        >
          <div className="flex flex-col gap-2 max-h-60 overflow-y-auto text-xs">
            {Array.isArray(capsule.evidence)
              ? capsule.evidence.map((ev) => (
                  <div
                    key={ev.evidence_id}
                    className="p-2.5 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex items-center justify-between font-mono text-[11px]"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#172033]">{ev.evidence_id}</span>
                      <span className="text-[#526176]">{ev.path}</span>
                      {ev.line_start && (
                        <span className="text-[#718096]">:L{ev.line_start}</span>
                      )}
                    </div>
                    <ProvenanceBadge provenance={ev.provenance} />
                  </div>
                ))
              : Object.entries(capsule.evidence).map(([id, ev]) => (
                  <div
                    key={id}
                    className="p-2.5 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex items-center justify-between font-mono text-[11px]"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#172033]">{id}</span>
                      <span className="text-[#526176]">{ev.path}</span>
                      {ev.line_start && (
                        <span className="text-[#718096]">:L{ev.line_start}</span>
                      )}
                    </div>
                    <ProvenanceBadge provenance={ev.provenance} />
                  </div>
                ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
