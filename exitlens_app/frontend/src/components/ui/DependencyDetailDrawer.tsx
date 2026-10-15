import React, { useEffect, useRef } from 'react';
import {
  X,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  MinusCircle,
  Cpu,
  MapPin,
  Lightbulb,
  ListChecks,
  TestTube,
  FlaskConical,
  Link2,
  AlertCircle,
  FileCode,
  Loader2,
} from 'lucide-react';
import { Button } from './Button';
import { StatusBadge, StatusVariant } from './StatusBadge';
import { DependencyDetailState } from '../../hooks/useDependencies';
import {
  DependencyDetailResponse,
  EvidenceProvenance,
  RiskSeverity,
  VerificationStatus,
} from '../../types/api';

interface DependencyDetailDrawerProps {
  open: boolean;
  onClose: () => void;
  dependencyName?: string;
  detailState: DependencyDetailState;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function severityVariant(severity?: RiskSeverity | null): StatusVariant {
  switch (severity) {
    case 'critical': return 'failure';
    case 'high': return 'failure';
    case 'medium': return 'warning';
    case 'low': return 'info';
    case 'info': return 'neutral';
    default: return 'neutral';
  }
}

function provenanceBadge(prov?: EvidenceProvenance | string) {
  const map: Record<string, { label: string; variant: StatusVariant }> = {
    OBSERVED: { label: 'Observed', variant: 'success' },
    INFERRED: { label: 'Inferred', variant: 'info' },
    AI_RECOMMENDATION: { label: 'AI Recommendation', variant: 'warning' },
    EXECUTION_RESULT: { label: 'Execution Result', variant: 'success' },
    NOT_VERIFIED: { label: 'Not Verified', variant: 'neutral' },
  };
  const entry = prov ? map[prov] : null;
  if (!entry) return null;
  return (
    <StatusBadge variant={entry.variant} size="sm">
      {entry.label}
    </StatusBadge>
  );
}

function verificationIcon(status?: VerificationStatus | string | null) {
  switch (status) {
    case 'PASSED': return <CheckCircle2 className="w-4 h-4 text-[#18794E]" />;
    case 'FAILED': return <XCircle className="w-4 h-4 text-[#B42318]" />;
    case 'ERROR': return <AlertCircle className="w-4 h-4 text-[#B42318]" />;
    case 'TIMED_OUT': return <Clock className="w-4 h-4 text-[#925C08]" />;
    case 'SKIPPED': return <MinusCircle className="w-4 h-4 text-[#718096]" />;
    case 'NOT_RUN': return <MinusCircle className="w-4 h-4 text-[#718096]" />;
    default: return <MinusCircle className="w-4 h-4 text-[#718096]" />;
  }
}

function SectionHeading({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 pb-2 border-b border-[#E1E6EE] mb-3">
      <span className="text-[#526176]">{icon}</span>
      <h3 className="text-xs font-semibold text-[#172033] uppercase tracking-wider">{title}</h3>
    </div>
  );
}

function CodeExcerpt({ code }: { code: string }) {
  return (
    <pre className="text-[11px] font-mono bg-[#F5F7FA] border border-[#E1E6EE] rounded p-2.5 overflow-x-auto whitespace-pre leading-relaxed text-[#172033] max-h-40">
      {code}
    </pre>
  );
}

function UnavailableSection({ reason }: { reason: string }) {
  return (
    <p className="text-xs text-[#718096] italic py-1">{reason}</p>
  );
}

// ─── Section renderers ───────────────────────────────────────────────────────

function RiskIndicatorsSection({ detail }: { detail: DependencyDetailResponse }) {
  const risks = detail.risk_indicators ?? [];
  return (
    <div>
      <SectionHeading icon={<AlertTriangle className="w-3.5 h-3.5" />} title="Risk Indicators" />
      {risks.length === 0 ? (
        <UnavailableSection reason="No risk indicators recorded for this dependency." />
      ) : (
        <div className="flex flex-col gap-3">
          {risks.map((r, i) => (
            <div key={i} className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-mono text-[11px] font-semibold text-[#172033]">{r.rule_id}</span>
                <StatusBadge variant={severityVariant(r.severity)} size="sm">
                  {r.severity?.toUpperCase() ?? 'UNKNOWN'}
                </StatusBadge>
              </div>
              <p className="text-xs text-[#526176] leading-relaxed">{r.signal}</p>
              {r.explanation && (
                <p className="text-[11px] text-[#718096] mt-1 leading-relaxed">{r.explanation}</p>
              )}
              {r.limitations && (
                <p className="text-[11px] text-[#925C08] mt-1 italic">{r.limitations}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UsageLocationsSection({ detail }: { detail: DependencyDetailResponse }) {
  const usages = detail.usage_locations ?? [];
  return (
    <div>
      <SectionHeading icon={<MapPin className="w-3.5 h-3.5" />} title="Usage Locations" />
      {usages.length === 0 ? (
        <UnavailableSection reason="No static usage locations located in the repository." />
      ) : (
        <div className="flex flex-col gap-2">
          {usages.map((u, i) => (
            <div key={i} className="text-xs border border-[#E1E6EE] rounded-md overflow-hidden">
              <div className="px-3 py-1.5 bg-[#F5F7FA] flex items-center justify-between gap-2">
                <span className="font-mono text-[#172033] truncate">{u.file_path}:{u.line_start}{u.line_end && u.line_end !== u.line_start ? `–${u.line_end}` : ''}</span>
                <div className="flex items-center gap-1.5 shrink-0">
                  {u.is_test_file && <StatusBadge variant="neutral" size="sm">test</StatusBadge>}
                  {provenanceBadge(u.provenance)}
                </div>
              </div>
              {u.excerpt && <CodeExcerpt code={u.excerpt} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProposedReplacementSection({ detail }: { detail: DependencyDetailResponse }) {
  const rep = detail.proposed_replacement;
  if (!rep) return (
    <div>
      <SectionHeading icon={<Lightbulb className="w-3.5 h-3.5" />} title="Proposed Replacement" />
      <UnavailableSection reason="No replacement assessment available." />
    </div>
  );
  return (
    <div>
      <SectionHeading icon={<Lightbulb className="w-3.5 h-3.5" />} title="Proposed Replacement" />
      <div className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-[#172033]">
            {rep.candidate_distribution ?? 'No candidate identified'}
            {rep.candidate_specifier ? ` ${rep.candidate_specifier}` : ''}
          </span>
          <div className="flex items-center gap-1.5">
            {provenanceBadge(rep.provenance)}
          </div>
        </div>
        {rep.rationale && <p className="text-xs text-[#526176] leading-relaxed">{rep.rationale}</p>}
        {rep.limitations && (
          <p className="text-[11px] text-[#925C08] italic leading-relaxed">{rep.limitations}</p>
        )}
      </div>
    </div>
  );
}

function MigrationStepsSection({ detail }: { detail: DependencyDetailResponse }) {
  const steps = detail.migration_steps ?? [];
  return (
    <div>
      <SectionHeading icon={<ListChecks className="w-3.5 h-3.5" />} title="Migration Steps" />
      {steps.length === 0 ? (
        <UnavailableSection reason="No migration steps available." />
      ) : (
        <ol className="flex flex-col gap-3">
          {steps.map((s, i) => (
            <li key={i} className="flex gap-3">
              <span className="shrink-0 w-5 h-5 rounded-full bg-[#EEF3FF] text-[#315BE8] text-[10px] font-bold flex items-center justify-center mt-0.5">
                {s.step_number ?? i + 1}
              </span>
              <div className="flex flex-col gap-1 flex-1 min-w-0">
                <p className="text-xs text-[#172033] leading-relaxed">{s.description}</p>
                {s.code_example && <CodeExcerpt code={s.code_example} />}
                {provenanceBadge(s.provenance)}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function SuggestedTestsSection({ detail }: { detail: DependencyDetailResponse }) {
  const tests = detail.suggested_tests ?? [];
  return (
    <div>
      <SectionHeading icon={<TestTube className="w-3.5 h-3.5" />} title="Suggested Tests" />
      {tests.length === 0 ? (
        <UnavailableSection reason="No test suggestions available." />
      ) : (
        <div className="flex flex-col gap-3">
          {tests.map((t, i) => (
            <div key={i} className="p-3 bg-[#FAFBFC] border border-[#E1E6EE] rounded-md flex flex-col gap-1">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-[#172033]">{t.description}</p>
                {provenanceBadge(t.provenance)}
              </div>
              {t.code_example && <CodeExcerpt code={t.code_example} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ExecutedResultsSection({ detail }: { detail: DependencyDetailResponse }) {
  const results = detail.executed_test_results ?? [];
  return (
    <div>
      <SectionHeading icon={<FlaskConical className="w-3.5 h-3.5" />} title="Executed Test Results" />
      {results.length === 0 ? (
        <UnavailableSection reason="Not run — no verification trials have been executed for this dependency." />
      ) : (
        <div className="flex flex-col gap-3">
          {results.map((r, i) => (
            <div key={i} className="border border-[#E1E6EE] rounded-md overflow-hidden">
              <div className="px-3 py-2 bg-[#F5F7FA] flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {verificationIcon(r.status)}
                  <span className="text-xs font-semibold text-[#172033]">
                    {r.is_baseline ? 'Baseline' : 'Replacement'} — {r.status}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  {r.duration_seconds != null && (
                    <span className="text-[11px] text-[#718096]">{r.duration_seconds.toFixed(1)}s</span>
                  )}
                  {provenanceBadge(r.provenance)}
                </div>
              </div>
              {r.profile_id && (
                <div className="px-3 py-1 text-[11px] text-[#526176] border-b border-[#E1E6EE]">
                  Profile: <span className="font-mono">{r.profile_id}</span>
                </div>
              )}
              {(r.stdout_excerpt || r.stderr_excerpt) && (
                <div className="p-2.5">
                  {r.stdout_excerpt && (
                    <CodeExcerpt code={`stdout:\n${r.stdout_excerpt}`} />
                  )}
                  {r.stderr_excerpt && (
                    <CodeExcerpt code={`stderr:\n${r.stderr_excerpt}`} />
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CompatibilityGapsSection({ detail }: { detail: DependencyDetailResponse }) {
  const gaps = detail.compatibility_gaps ?? [];
  return (
    <div>
      <SectionHeading icon={<Link2 className="w-3.5 h-3.5" />} title="Compatibility Gaps" />
      {gaps.length === 0 ? (
        <UnavailableSection reason="No compatibility gaps identified." />
      ) : (
        <div className="flex flex-col gap-2">
          {gaps.map((g, i) => (
            <div key={i} className="flex items-start gap-2 text-xs p-2.5 bg-[#FFF5DE] border border-[#FDE4A4] rounded-md">
              <AlertTriangle className="w-3.5 h-3.5 text-[#925C08] shrink-0 mt-0.5" />
              <div>
                <p className="text-[#172033]">{g.description}</p>
                {provenanceBadge(g.provenance)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function OpenConcernsSection({ detail }: { detail: DependencyDetailResponse }) {
  const concerns = detail.open_concerns_limitations ?? [];
  return (
    <div>
      <SectionHeading icon={<AlertCircle className="w-3.5 h-3.5" />} title="Open Concerns & Limitations" />
      {concerns.length === 0 ? (
        <UnavailableSection reason="No open concerns or limitations recorded." />
      ) : (
        <ul className="flex flex-col gap-2">
          {concerns.map((c, i) => (
            <li key={i} className="flex items-start gap-2 text-xs">
              <span className="text-[#718096] shrink-0 mt-0.5">•</span>
              <span className="text-[#526176] leading-relaxed">{c.description}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ─── Main Drawer ─────────────────────────────────────────────────────────────

export function DependencyDetailDrawer({
  open,
  onClose,
  dependencyName,
  detailState,
}: DependencyDetailDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  // Trap focus & close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  // Prevent body scroll while open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/20 transition-opacity duration-200 ${open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Dependency detail: ${dependencyName ?? 'Loading...'}`}
        className={`fixed top-0 right-0 z-50 h-full w-full max-w-2xl bg-white shadow-2xl flex flex-col transition-transform duration-200 ease-out ${open ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Drawer header */}
        <div className="px-5 py-4 border-b border-[#E1E6EE] flex items-center justify-between gap-4 shrink-0 bg-white">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-md bg-[#EEF3FF] flex items-center justify-center shrink-0">
              <FileCode className="w-4 h-4 text-[#315BE8]" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-[#172033] truncate">
                {dependencyName ?? 'Dependency Detail'}
              </h2>
              <p className="text-xs text-[#718096]">All nine capsule sections</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            icon={<X className="w-4 h-4" />}
            aria-label="Close detail panel"
          >
            Close
          </Button>
        </div>

        {/* Drawer body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-7">
          {detailState.status === 'loading' && (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-[#526176]">
              <Loader2 className="w-6 h-6 animate-spin text-[#315BE8]" />
              <span className="text-sm">Loading dependency detail...</span>
            </div>
          )}

          {detailState.status === 'error' && (
            <div className="p-4 bg-[#FEF0F0] border border-[#FECDCA] rounded-lg flex items-start gap-3 text-xs text-[#B42318]">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block mb-1">Failed to load [{detailState.code}]</span>
                <span>{detailState.error}</span>
              </div>
            </div>
          )}

          {detailState.status === 'loaded' && (() => {
            const d = detailState.detail;
            const dd = d.dependency_details ?? {};
            return (
              <>
                {/* Section 1 — dependency_details */}
                <div>
                  <SectionHeading icon={<Cpu className="w-3.5 h-3.5" />} title="Dependency Details" />
                  <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
                    {([
                      ['Distribution', dd.distribution_name ?? dd.name],
                      ['Declared Version', dd.declared_version ?? '—'],
                      ['Resolved Version', dd.resolved_version ?? '—'],
                      ['Manifest', dd.manifest_path ?? (dd.manifest_paths as string[] | undefined)?.join(', ') ?? '—'],
                    ] as [string, string][]).map(([label, value]) => (
                      <div key={label}>
                        <span className="text-[#718096]">{label}</span>
                        <p className="font-mono font-medium text-[#172033] truncate mt-0.5" title={value}>{value}</p>
                      </div>
                    ))}
                    {dd.summary && (
                      <div className="col-span-2">
                        <span className="text-[#718096]">Summary</span>
                        <p className="text-[#526176] mt-0.5 leading-relaxed">{dd.summary as string}</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Sections 2–9 */}
                <RiskIndicatorsSection detail={d} />
                <UsageLocationsSection detail={d} />
                <ProposedReplacementSection detail={d} />
                <MigrationStepsSection detail={d} />
                <SuggestedTestsSection detail={d} />
                <ExecutedResultsSection detail={d} />
                <CompatibilityGapsSection detail={d} />
                <OpenConcernsSection detail={d} />

                {/* Warnings */}
                {d.warnings && d.warnings.length > 0 && (
                  <div className="p-3 bg-[#FFF5DE] border border-[#FDE4A4] rounded-md text-xs text-[#925C08]">
                    <span className="font-semibold block mb-1">Scanner Coverage Notes</span>
                    <ul className="list-disc list-inside space-y-0.5">
                      {d.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </div>
                )}
              </>
            );
          })()}
        </div>
      </div>
    </>
  );
}
