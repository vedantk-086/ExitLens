import { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  SearchCode,
  ArrowLeft,
  Filter,
  RotateCcw,
  RefreshCw,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,

  ChevronRight,
  Loader2,
  PackageSearch,
  ShieldAlert,
  ArrowRight,
  X,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge, StatusVariant } from '../components/ui/StatusBadge';
import { Input } from '../components/ui/Input';
import { DependencyDetailDrawer } from '../components/ui/DependencyDetailDrawer';
import { useAnalysisContext } from '../context/useAnalysisContext';
import { useDependencyList, useDependencyDetail } from '../hooks/useDependencies';
import { postRecommendations } from '../api/analyses';
import { ApiClientError } from '../api/client';
import { RunStatus, DependencyListItem, RiskSeverity, RecommendationStatus } from '../types/api';

// ─── Helpers ────────────────────────────────────────────────────────────────

const TERMINAL_STATUSES: RunStatus[] = [
  'completed', 'completed_with_warnings', 'failed', 'ready_for_verification',
];

function isTerminal(status: RunStatus) {
  return TERMINAL_STATUSES.includes(status);
}

function severityVariant(severity?: RiskSeverity | null): StatusVariant {
  switch (severity) {
    case 'critical':
    case 'high': return 'failure';
    case 'medium': return 'warning';
    case 'low': return 'info';
    case 'info': return 'neutral';
    default: return 'neutral';
  }
}

function recVariant(status?: RecommendationStatus | string | null): StatusVariant {
  switch (status) {
    case 'available': return 'success';
    case 'pending':
    case 'generating': return 'info';
    case 'error': return 'failure';
    case 'unavailable':
    case 'no_candidate_identified': return 'neutral';
    case 'not_requested': return 'neutral';
    default: return 'neutral';
  }
}

function verificationVariant(status?: string | null): StatusVariant {
  switch (status) {
    case 'PASSED': return 'success';
    case 'FAILED':
    case 'ERROR': return 'failure';
    case 'TIMED_OUT': return 'warning';
    case 'SKIPPED':
    case 'NOT_RUN': return 'neutral';
    default: return 'neutral';
  }
}

function formatLabel(s: string) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatStageLabel(stage: string) {
  return stage.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// ─── Sort types ──────────────────────────────────────────────────────────────

type SortField = 'name' | 'highest_severity' | 'usage_count' | 'recommendation_status';
type SortDir = 'asc' | 'desc';

const SEVERITY_ORDER: Record<string, number> = {
  critical: 4, high: 3, medium: 2, low: 1, info: 0,
};

function sortItems(items: DependencyListItem[], field: SortField, dir: SortDir) {
  return [...items].sort((a, b) => {
    let cmp = 0;
    if (field === 'name') {
      cmp = a.name.localeCompare(b.name);
    } else if (field === 'highest_severity') {
      const av = SEVERITY_ORDER[a.highest_severity ?? ''] ?? -1;
      const bv = SEVERITY_ORDER[b.highest_severity ?? ''] ?? -1;
      cmp = bv - av; // highest first by default
    } else if (field === 'usage_count') {
      cmp = (b.usage_count ?? 0) - (a.usage_count ?? 0);
    } else if (field === 'recommendation_status') {
      cmp = (a.recommendation_status ?? '').localeCompare(b.recommendation_status ?? '');
    }
    return dir === 'asc' ? cmp : -cmp;
  });
}

// ─── SortButton ──────────────────────────────────────────────────────────────

function SortButton({
  label, field, current, dir, onSort,
}: {
  label: string;
  field: SortField;
  current: SortField;
  dir: SortDir;
  onSort: (f: SortField) => void;
}) {
  const active = current === field;
  return (
    <button
      type="button"
      onClick={() => onSort(field)}
      className="flex items-center gap-1 text-xs font-semibold text-[#526176] hover:text-[#172033] transition-colors select-none"
    >
      {label}
      <span className="text-[#CCD5E2]">
        {active ? (dir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : <ChevronsUpDown className="w-3 h-3" />}
      </span>
    </button>
  );
}

// ─── Recommendation retry panel ───────────────────────────────────────────────

function RecommendationRetryPanel({
  analysisId,
  selectedIds,
  onRefresh,
}: {
  analysisId: string;
  selectedIds: string[];
  onRefresh: () => void;
}) {
  const [status, setStatus] = useState<'idle' | 'submitting' | 'done' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const handleRetry = async () => {
    setStatus('submitting');
    setErrorMsg('');
    try {
      await postRecommendations(analysisId, {
        dependency_ids: selectedIds,
        force_regenerate: false,
      });
      setStatus('done');
      setTimeout(() => { setStatus('idle'); onRefresh(); }, 2000);
    } catch (err) {
      setErrorMsg(err instanceof ApiClientError ? err.message : 'Request failed.');
      setStatus('error');
    }
  };

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-[#EEF3FF] border border-[#C6D8FF] rounded-md text-xs">
      <span className="text-[#2648C7]">
        {selectedIds.length} dependenc{selectedIds.length === 1 ? 'y' : 'ies'} selected
      </span>
      {status === 'error' && (
        <span className="text-[#B42318]">{errorMsg}</span>
      )}
      {status === 'done' && (
        <span className="text-[#18794E] flex items-center gap-1">
          <CheckCircle2 className="w-3.5 h-3.5" /> Queued
        </span>
      )}
      <Button
        size="sm"
        variant="subtle"
        isLoading={status === 'submitting'}
        disabled={status === 'submitting' || status === 'done' || selectedIds.length === 0}
        onClick={handleRetry}
      >
        Retry Recommendations
      </Button>
    </div>
  );
}

// ─── Dependency table row ────────────────────────────────────────────────────

function DepRow({
  dep,
  selected,
  onSelect,
  onOpen,
}: {
  dep: DependencyListItem;
  selected: boolean;
  onSelect: (id: string, checked: boolean) => void;
  onOpen: (dep: DependencyListItem) => void;
}) {
  return (
    <tr
      className="border-b border-[#E1E6EE] hover:bg-[#F5F7FA] transition-colors duration-100 group"
    >
      {/* Select checkbox */}
      <td className="pl-4 pr-2 py-2.5 w-8">
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => onSelect(dep.dependency_id, e.target.checked)}
          className="h-3.5 w-3.5 rounded border-[#CCD5E2] text-[#315BE8] focus:ring-[#315BE8] cursor-pointer"
          aria-label={`Select ${dep.name}`}
        />
      </td>

      {/* Name */}
      <td className="pr-3 py-2.5 min-w-[140px] max-w-[200px]">
        <div className="flex items-center gap-1.5">
          {dep.is_flagged && (
            <ShieldAlert className="w-3.5 h-3.5 text-[#B42318] shrink-0" aria-label="Flagged" />
          )}
          <span className="font-mono text-xs font-semibold text-[#172033] truncate" title={dep.name}>
            {dep.name}
          </span>
        </div>
      </td>

      {/* Declared version */}
      <td className="pr-3 py-2.5 w-32 hidden sm:table-cell">
        <span className="font-mono text-xs text-[#526176]" title={dep.declared_version ?? undefined}>
          {dep.declared_version ?? <span className="text-[#A0AEC0]">—</span>}
        </span>
      </td>

      {/* Resolved version */}
      <td className="pr-3 py-2.5 w-32 hidden md:table-cell">
        <span className="font-mono text-xs text-[#526176]">
          {dep.resolved_version ?? <span className="text-[#A0AEC0]">—</span>}
        </span>
      </td>

      {/* Severity */}
      <td className="pr-3 py-2.5 w-28">
        {dep.highest_severity ? (
          <StatusBadge variant={severityVariant(dep.highest_severity)} size="sm">
            {dep.highest_severity.toUpperCase()}
          </StatusBadge>
        ) : (
          <span className="text-xs text-[#A0AEC0]">—</span>
        )}
      </td>

      {/* Risk rules */}
      <td className="pr-3 py-2.5 min-w-[100px] max-w-[180px] hidden lg:table-cell">
        <div className="flex flex-wrap gap-1">
          {dep.risk_rule_ids && dep.risk_rule_ids.length > 0 ? (
            dep.risk_rule_ids.slice(0, 2).map((rule) => (
              <span
                key={rule}
                className="font-mono text-[10px] px-1 py-0.5 bg-[#EEF1F5] text-[#526176] rounded"
                title={rule}
              >
                {rule.length > 24 ? rule.slice(0, 22) + '…' : rule}
              </span>
            ))
          ) : (
            <span className="text-xs text-[#A0AEC0]">—</span>
          )}
          {dep.risk_rule_ids && dep.risk_rule_ids.length > 2 && (
            <span className="text-[10px] text-[#718096]">+{dep.risk_rule_ids.length - 2}</span>
          )}
        </div>
      </td>

      {/* Manifest path */}
      <td className="pr-3 py-2.5 max-w-[160px] hidden xl:table-cell">
        <span className="font-mono text-[11px] text-[#718096] truncate block" title={dep.manifest_path}>
          {dep.manifest_path ?? <span className="text-[#A0AEC0]">—</span>}
        </span>
      </td>

      {/* Usages */}
      <td className="pr-3 py-2.5 w-16 text-center hidden sm:table-cell">
        <span className="text-xs text-[#526176]">
          {dep.usage_count ?? <span className="text-[#A0AEC0]">—</span>}
        </span>
      </td>

      {/* Recommendation */}
      <td className="pr-3 py-2.5 w-32 hidden md:table-cell">
        {dep.recommendation_status ? (
          <StatusBadge variant={recVariant(dep.recommendation_status)} size="sm">
            {formatLabel(dep.recommendation_status)}
          </StatusBadge>
        ) : (
          <span className="text-xs text-[#A0AEC0]">—</span>
        )}
      </td>

      {/* Verification */}
      <td className="pr-3 py-2.5 w-28 hidden lg:table-cell">
        {dep.verification_status ? (
          <StatusBadge variant={verificationVariant(dep.verification_status as string)} size="sm">
            {dep.verification_status}
          </StatusBadge>
        ) : (
          <span className="text-xs text-[#A0AEC0]">—</span>
        )}
      </td>

      {/* Action */}
      <td className="pr-4 py-2.5 w-16 text-right">
        <button
          type="button"
          onClick={() => onOpen(dep)}
          className="text-[#315BE8] hover:text-[#2648C7] transition-colors p-1 rounded hover:bg-[#EEF3FF]"
          aria-label={`Inspect ${dep.name}`}
          title="Inspect dependency"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </td>
    </tr>
  );
}

// ─── Main Analysis Page ──────────────────────────────────────────────────────

export function AnalysisPage() {
  const navigate = useNavigate();
  const { activeAnalysis, isPolling, resetActiveAnalysis, setSelectedDependencyIds } = useAnalysisContext();

  const analysisId = activeAnalysis?.analysis_id ?? null;
  const readyToLoad = analysisId !== null && (
    activeAnalysis == null || isTerminal(activeAnalysis.status)
  );

  const { state: listState, refresh } = useDependencyList(readyToLoad ? analysisId : null);

  // Filters
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [recFilter, setRecFilter] = useState<string>('');
  const [verFilter, setVerFilter] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('highest_severity');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Selection for recommendation retry & verification
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Drawer
  const [drawerDep, setDrawerDep] = useState<DependencyListItem | null>(null);
  const drawerOpen = drawerDep !== null;
  const detailState = useDependencyDetail(analysisId, drawerDep?.dependency_id ?? null);

  const closeDrawer = useCallback(() => setDrawerDep(null), []);

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const handleSelect = (id: string, checked: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (checked) next.add(id); else next.delete(id);
      setSelectedDependencyIds([...next]);
      return next;
    });
  };

  // Derive unique filter options from loaded data
  const allItems = listState.status === 'loaded' ? listState.items : [];
  const severities = useMemo(() => {
    const s = new Set(allItems.map(d => d.highest_severity).filter(Boolean) as string[]);
    return [...s].sort((a, b) => (SEVERITY_ORDER[b] ?? 0) - (SEVERITY_ORDER[a] ?? 0));
  }, [allItems]);
  const recStatuses = useMemo(() => {
    const s = new Set(allItems.map(d => d.recommendation_status).filter(Boolean) as string[]);
    return [...s];
  }, [allItems]);
  const verStatuses = useMemo(() => {
    const s = new Set(allItems.map(d => d.verification_status).filter(Boolean) as string[]);
    return [...s];
  }, [allItems]);

  // Filtered + sorted items
  const filteredItems = useMemo(() => {
    let items = allItems;
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(d =>
        d.name.toLowerCase().includes(q) ||
        d.manifest_path?.toLowerCase().includes(q) ||
        d.risk_rule_ids?.some(r => r.toLowerCase().includes(q))
      );
    }
    if (severityFilter) items = items.filter(d => d.highest_severity === severityFilter);
    if (recFilter) items = items.filter(d => d.recommendation_status === recFilter);
    if (verFilter) items = items.filter(d => d.verification_status === verFilter);
    return sortItems(items, sortField, sortDir);
  }, [allItems, search, severityFilter, recFilter, verFilter, sortField, sortDir]);

  const hasFilters = Boolean(search || severityFilter || recFilter || verFilter);
  const clearFilters = () => { setSearch(''); setSeverityFilter(''); setRecFilter(''); setVerFilter(''); };

  // Summary from analysis status (already available from context)
  const summary = activeAnalysis?.summary;

  // Status variant helper
  const getStatusVariant = (status: RunStatus): StatusVariant => {
    switch (status) {
      case 'completed': return 'success';
      case 'completed_with_warnings':
      case 'ready_for_verification': return 'warning';
      case 'failed': return 'failure';
      default: return 'info';
    }
  };

  // ─── Render states ──────────────────────────────────────────────────────────

  // No active analysis
  if (!activeAnalysis) {
    return (
      <div className="flex flex-col gap-6 animate-in fade-in duration-200">
        <PageHeader
          title="Dependency Analysis & Inventory"
          description="Inspect discovered dependencies, static import usages, maintenance risk indicators, and Gemma 4 migration plans."
          badge={<StatusBadge variant="neutral" size="sm">No Active Run</StatusBadge>}
          breadcrumbs={[{ label: 'Workbench' }, { label: 'Analysis' }]}
          actions={
            <Button variant="outline" size="sm" onClick={() => navigate('/workspace')} icon={<ArrowLeft className="w-3.5 h-3.5" />}>
              Back to Workspace
            </Button>
          }
        />
        <Panel title="Discovered Dependencies & Risk Inventory" subtitle="Run an analysis from the Workspace to populate this inventory.">
          <EmptyState
            icon={<SearchCode className="w-6 h-6" />}
            title="No Active Repository Analysis"
            description="Dependency findings, static usage mapping, and Gemma 4 migration recommendations will be populated here after an analysis is initiated from the Workspace."
            action={
              <Button variant="primary" size="sm" onClick={() => navigate('/workspace')} icon={<PackageSearch className="w-3.5 h-3.5" />}>
                Configure Repository Scan
              </Button>
            }
          />
        </Panel>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 animate-in fade-in duration-200">
      {/* Page header */}
      <PageHeader
        title="Dependency Analysis & Inventory"
        description="Dependencies assessed from repository declarations, static usage mapping, and evidence-backed maintenance indicators."
        badge={
          <StatusBadge variant={getStatusVariant(activeAnalysis.status)} size="sm" dot={isPolling}>
            {formatStageLabel(activeAnalysis.status)}
          </StatusBadge>
        }
        breadcrumbs={[{ label: 'Workbench' }, { label: 'Analysis' }]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { resetActiveAnalysis(); navigate('/workspace'); }}
              icon={<RotateCcw className="w-3.5 h-3.5" />}
            >
              Reset Run
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/workspace')}
              icon={<ArrowLeft className="w-3.5 h-3.5" />}
            >
              Workspace
            </Button>
          </div>
        }
      />

      {/* Analysis running banner */}
      {!isTerminal(activeAnalysis.status) && (
        <div className="p-3.5 bg-[#EEF3FF] border border-[#C6D8FF] rounded-lg flex items-center gap-3 text-xs text-[#2648C7]">
          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
          <span>
            Analysis in progress — <strong>{formatStageLabel(activeAnalysis.stage || activeAnalysis.status)}</strong>.
            The inventory will load once scanning completes.
          </span>
          <Button size="sm" variant="subtle" onClick={refresh} icon={<RefreshCw className="w-3 h-3" />} className="ml-auto shrink-0">
            Refresh
          </Button>
        </div>
      )}

      {/* Warnings from analysis */}
      {activeAnalysis.warnings && activeAnalysis.warnings.length > 0 && (
        <div className="p-3 bg-[#FFF5DE] border border-[#FDE4A4] rounded-lg flex items-start gap-2.5 text-xs text-[#925C08]">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Scanner Coverage Notes: </span>
            {activeAnalysis.warnings.join(' · ')}
          </div>
        </div>
      )}

      {/* Summary strip */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Discovered', value: summary.dependencies_discovered, color: 'text-[#172033]', bg: 'bg-white' },
            { label: 'Flagged', value: summary.dependencies_flagged, color: 'text-[#B42318]', bg: 'bg-[#FEF0F0]' },
            { label: 'Gemma 4 Plans', value: summary.recommendations_available, color: 'text-[#315BE8]', bg: 'bg-[#EEF3FF]' },
            { label: 'Checks Passed', value: summary.checks_passed, color: 'text-[#18794E]', bg: 'bg-[#EAF7EF]' },
          ].map(({ label, value, color, bg }) => (
            <div key={label} className={`${bg} border border-[#E1E6EE] rounded-lg p-3 text-center`}>
              <div className={`text-xl font-bold ${color}`}>{value}</div>
              <div className="text-[10px] uppercase text-[#718096] tracking-wide mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Inventory panel */}
      <Panel
        padded={false}
        title="Dependency Inventory"
        subtitle={
          listState.status === 'loaded'
            ? `${filteredItems.length} of ${allItems.length} dependencies${hasFilters ? ' (filtered)' : ''}`
            : 'Retrieving inventory from backend…'
        }
        actions={
          <div className="flex items-center gap-2">
            {listState.status === 'loaded' && (
              <button
                type="button"
                onClick={refresh}
                className="p-1.5 rounded text-[#718096] hover:text-[#172033] hover:bg-[#EEF1F5] transition-colors"
                title="Refresh inventory"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                if (selectedIds.size > 0) {
                  setSelectedDependencyIds([...selectedIds]);
                }
                navigate('/verification');
              }}
              icon={<ArrowRight className="w-3.5 h-3.5" />}
              iconPosition="right"
            >
              Verification
            </Button>
          </div>
        }
      >
        {/* Toolbar */}
        {listState.status === 'loaded' && allItems.length > 0 && (
          <div className="px-5 py-3 border-b border-[#E1E6EE] flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="flex-1 min-w-48 max-w-72">
              <Input
                placeholder="Search name, manifest, rule…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                leftIcon={<Filter className="w-3.5 h-3.5" />}
                rightIcon={search ? (
                  <button type="button" onClick={() => setSearch('')} className="pointer-events-auto">
                    <X className="w-3.5 h-3.5 text-[#718096] hover:text-[#172033]" />
                  </button>
                ) : null}
                className="h-8 text-xs"
              />
            </div>

            {/* Severity filter */}
            {severities.length > 0 && (
              <select
                value={severityFilter}
                onChange={e => setSeverityFilter(e.target.value)}
                className="h-8 text-xs border border-[#E1E6EE] rounded-md px-2 bg-white text-[#526176] hover:border-[#CCD5E2] focus:outline-none focus:ring-1 focus:ring-[#315BE8] cursor-pointer"
                aria-label="Filter by severity"
              >
                <option value="">All Severities</option>
                {severities.map(s => (
                  <option key={s} value={s}>{s.toUpperCase()}</option>
                ))}
              </select>
            )}

            {/* Recommendation filter */}
            {recStatuses.length > 0 && (
              <select
                value={recFilter}
                onChange={e => setRecFilter(e.target.value)}
                className="h-8 text-xs border border-[#E1E6EE] rounded-md px-2 bg-white text-[#526176] hover:border-[#CCD5E2] focus:outline-none focus:ring-1 focus:ring-[#315BE8] cursor-pointer"
                aria-label="Filter by recommendation"
              >
                <option value="">All Recs</option>
                {recStatuses.map(s => (
                  <option key={s} value={s}>{formatLabel(s)}</option>
                ))}
              </select>
            )}

            {/* Verification filter */}
            {verStatuses.length > 0 && (
              <select
                value={verFilter}
                onChange={e => setVerFilter(e.target.value)}
                className="h-8 text-xs border border-[#E1E6EE] rounded-md px-2 bg-white text-[#526176] hover:border-[#CCD5E2] focus:outline-none focus:ring-1 focus:ring-[#315BE8] cursor-pointer"
                aria-label="Filter by verification"
              >
                <option value="">All Verification</option>
                {verStatuses.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            )}

            {/* Clear */}
            {hasFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="flex items-center gap-1 text-xs text-[#718096] hover:text-[#B42318] transition-colors"
              >
                <X className="w-3.5 h-3.5" />
                Clear
              </button>
            )}

            {/* Retry recommendations */}
            {selectedIds.size > 0 && analysisId && (
              <div className="ml-auto">
                <RecommendationRetryPanel
                  analysisId={analysisId}
                  selectedIds={[...selectedIds]}
                  onRefresh={refresh}
                />
              </div>
            )}
          </div>
        )}

        {/* States */}
        {listState.status === 'idle' && isTerminal(activeAnalysis.status) && (
          <div className="p-6 flex justify-center">
            <Button variant="outline" size="sm" onClick={refresh} icon={<RefreshCw className="w-3.5 h-3.5" />}>
              Load Inventory
            </Button>
          </div>
        )}

        {listState.status === 'loading' && (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-[#526176]">
            <Loader2 className="w-6 h-6 animate-spin text-[#315BE8]" />
            <span className="text-sm">Loading dependency inventory…</span>
          </div>
        )}

        {listState.status === 'error' && (
          <div className="p-5">
            <div className="p-4 bg-[#FEF0F0] border border-[#FECDCA] rounded-lg flex items-start gap-3 text-xs text-[#B42318]">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-semibold block mb-1">Inventory Unavailable [{listState.code}]</span>
                <span className="leading-relaxed">{listState.error}</span>
                {listState.code === 'HTTP_404' && (
                  <p className="mt-2 text-[#526176]">The analysis ID may be invalid or expired. Return to Workspace to start a new scan.</p>
                )}
                {listState.code === 'NETWORK_ERROR' && (
                  <p className="mt-2 text-[#526176]">Check that the FastAPI backend is running at the configured address.</p>
                )}
              </div>
              <Button variant="ghost" size="sm" onClick={refresh} icon={<RefreshCw className="w-3.5 h-3.5" />}>
                Retry
              </Button>
            </div>
          </div>
        )}

        {listState.status === 'loaded' && allItems.length === 0 && (
          <div className="p-6">
            <EmptyState
              icon={<CheckCircle2 className="w-6 h-6" />}
              title="No Dependencies Discovered"
              description="The scanner did not discover any declared dependencies in the repository. Check scanner coverage warnings or review manifest file support."
              action={
                <Button variant="outline" size="sm" onClick={refresh} icon={<RefreshCw className="w-3.5 h-3.5" />}>
                  Refresh
                </Button>
              }
            />
          </div>
        )}

        {listState.status === 'loaded' && allItems.length > 0 && filteredItems.length === 0 && (
          <div className="p-6">
            <EmptyState
              compact
              icon={<Filter className="w-5 h-5" />}
              title="No Matching Dependencies"
              description="No dependencies match the active search and filter criteria."
              action={
                <Button variant="ghost" size="sm" onClick={clearFilters} icon={<X className="w-3.5 h-3.5" />}>
                  Clear Filters
                </Button>
              }
            />
          </div>
        )}

        {/* Warnings from inventory */}
        {listState.status === 'loaded' && listState.warnings.length > 0 && (
          <div className="px-5 py-2 bg-[#FFF5DE] border-b border-[#FDE4A4] flex items-start gap-2 text-[11px] text-[#925C08]">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>{listState.warnings.join(' · ')}</span>
          </div>
        )}

        {/* Table */}
        {listState.status === 'loaded' && filteredItems.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[#E1E6EE] bg-[#F5F7FA]">
                  <th className="pl-4 pr-2 py-2.5 w-8">
                    <input
                      type="checkbox"
                      onChange={(e) => {
                        if (e.target.checked) {
                          const all = new Set(filteredItems.map(d => d.dependency_id));
                          setSelectedIds(all);
                          setSelectedDependencyIds([...all]);
                        } else {
                          setSelectedIds(new Set());
                          setSelectedDependencyIds([]);
                        }
                      }}
                      checked={selectedIds.size === filteredItems.length && filteredItems.length > 0}
                      className="h-3.5 w-3.5 rounded border-[#CCD5E2] text-[#315BE8] focus:ring-[#315BE8] cursor-pointer"
                      aria-label="Select all"
                    />
                  </th>
                  <th className="pr-3 py-2.5">
                    <SortButton label="Package" field="name" current={sortField} dir={sortDir} onSort={handleSort} />
                  </th>
                  <th className="pr-3 py-2.5 hidden sm:table-cell">
                    <span className="text-xs font-semibold text-[#526176]">Declared</span>
                  </th>
                  <th className="pr-3 py-2.5 hidden md:table-cell">
                    <span className="text-xs font-semibold text-[#526176]">Resolved</span>
                  </th>
                  <th className="pr-3 py-2.5">
                    <SortButton label="Severity" field="highest_severity" current={sortField} dir={sortDir} onSort={handleSort} />
                  </th>
                  <th className="pr-3 py-2.5 hidden lg:table-cell">
                    <span className="text-xs font-semibold text-[#526176]">Rules</span>
                  </th>
                  <th className="pr-3 py-2.5 hidden xl:table-cell">
                    <span className="text-xs font-semibold text-[#526176]">Manifest</span>
                  </th>
                  <th className="pr-3 py-2.5 hidden sm:table-cell text-center">
                    <SortButton label="Usages" field="usage_count" current={sortField} dir={sortDir} onSort={handleSort} />
                  </th>
                  <th className="pr-3 py-2.5 hidden md:table-cell">
                    <SortButton label="Rec." field="recommendation_status" current={sortField} dir={sortDir} onSort={handleSort} />
                  </th>
                  <th className="pr-3 py-2.5 hidden lg:table-cell">
                    <span className="text-xs font-semibold text-[#526176]">Verification</span>
                  </th>
                  <th className="pr-4 py-2.5 text-right">
                    <span className="text-xs font-semibold text-[#526176]">Detail</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((dep) => (
                  <DepRow
                    key={dep.dependency_id}
                    dep={dep}
                    selected={selectedIds.has(dep.dependency_id)}
                    onSelect={handleSelect}
                    onOpen={setDrawerDep}
                  />
                ))}
              </tbody>
            </table>

            {/* Footer with result range */}
            <div className="px-4 py-2.5 border-t border-[#E1E6EE] bg-[#F5F7FA] flex items-center justify-between text-xs text-[#718096]">
              <span>
                Showing {filteredItems.length} of {allItems.length} dependencies
                {hasFilters ? ' (filtered)' : ''}
              </span>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    if (selectedIds.size > 0) {
                      setSelectedDependencyIds([...selectedIds]);
                    }
                    navigate('/verification');
                  }}
                  className="text-[#315BE8] hover:underline flex items-center gap-1"
                >
                  Continue to Verification <ArrowRight className="w-3 h-3" />
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/capsule')}
                  className="text-[#526176] hover:text-[#315BE8] hover:underline flex items-center gap-1"
                >
                  View Capsule <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Analysis still running but we can try loading */}
        {listState.status === 'idle' && !isTerminal(activeAnalysis.status) && (
          <div className="p-6 text-center text-xs text-[#718096]">
            The inventory endpoint will be available once the analysis scan completes.
          </div>
        )}
      </Panel>

      {/* Dependency detail drawer */}
      <DependencyDetailDrawer
        open={drawerOpen}
        onClose={closeDrawer}
        dependencyName={drawerDep?.name}
        detailState={detailState}
      />
    </div>
  );
}
