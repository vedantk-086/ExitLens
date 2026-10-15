import React from 'react';
import {
  FileSearch,
  AlertTriangle,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Package,
  XCircle,
  Loader2,
  Clock,
} from 'lucide-react';
import { AnalysisStatusResponse } from '../../types/api';

// ─── The Five Visual Stages ───────────────────────────────────────────────────

export interface ProgressStage {
  id: string;
  label: string;
  sublabel: string;
  backendStates: string[];
  icon: React.ReactNode;
}

export const FIVE_STAGES: ProgressStage[] = [
  {
    id: 'inspect',
    label: '1. Inspect',
    sublabel: 'Manifests & AST',
    backendStates: ['validating_repository', 'scanning', 'mapping_usage'],
    icon: <FileSearch className="w-4 h-4" />,
  },
  {
    id: 'assess',
    label: '2. Assess',
    sublabel: 'Risk Signals',
    backendStates: ['assessing_risk'],
    icon: <AlertTriangle className="w-4 h-4" />,
  },
  {
    id: 'recommend',
    label: '3. Recommend',
    sublabel: 'Gemma 4 Plans',
    backendStates: ['generating_recommendations'],
    icon: <Sparkles className="w-4 h-4" />,
  },
  {
    id: 'verify',
    label: '4. Verify',
    sublabel: 'Approved Runs',
    backendStates: ['ready_for_verification', 'verifying'],
    icon: <ShieldCheck className="w-4 h-4" />,
  },
  {
    id: 'package',
    label: '5. Package',
    sublabel: 'Exit Capsule',
    backendStates: ['completed', 'completed_with_warnings'],
    icon: <Package className="w-4 h-4" />,
  },
];

type NodeStatus = 'pending' | 'active' | 'completed' | 'failed' | 'warning';

function resolveNodeStatus(
  stageIndex: number,
  analysis: AnalysisStatusResponse | null
): NodeStatus {
  if (!analysis) return 'pending';

  const backendStatus = analysis.status;
  const backendStage = analysis.stage || analysis.status;

  // Queued run: waiting to begin
  if (backendStatus === 'queued') {
    return 'pending';
  }

  // Find which of the 5 visual stages the backend is currently at
  let currentStageIndex = -1;
  for (let i = FIVE_STAGES.length - 1; i >= 0; i--) {
    if (
      FIVE_STAGES[i].backendStates.includes(backendStatus) ||
      FIVE_STAGES[i].backendStates.includes(backendStage)
    ) {
      currentStageIndex = i;
      break;
    }
  }

  // Failed state
  if (backendStatus === 'failed') {
    if (stageIndex === currentStageIndex) return 'failed';
    if (stageIndex < currentStageIndex) return 'completed';
    return 'pending';
  }

  // Completed with warnings
  if (backendStatus === 'completed_with_warnings') {
    if (stageIndex === 4) return 'warning';
    return 'completed';
  }

  // Fully completed
  if (backendStatus === 'completed') {
    // Stage 5 is complete if capsule artifact is confirmed available or run completed
    return 'completed';
  }

  // Active or pending stages
  if (currentStageIndex === -1) return 'pending';
  if (stageIndex < currentStageIndex) return 'completed';
  if (stageIndex === currentStageIndex) {
    // If ready_for_verification, verification is optional and pending human approval
    if (backendStatus === 'ready_for_verification' || backendStage === 'ready_for_verification') {
      return 'active';
    }
    return 'active';
  }
  return 'pending';
}

// ─── Component ─────────────────────────────────────────────────────────────────

interface AnalysisProgressProps {
  analysis: AnalysisStatusResponse | null;
  className?: string;
}

export function AnalysisProgress({ analysis, className = '' }: AnalysisProgressProps) {
  if (!analysis) return null;

  const stageStatuses = FIVE_STAGES.map((_, i) =>
    resolveNodeStatus(i, analysis)
  );

  const activeIndex = stageStatuses.findIndex((s) => s === 'active');
  const isQueued = analysis.status === 'queued';

  return (
    <div className={`w-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <div className={`w-2.5 h-2.5 rounded-full ${
            analysis.status === 'failed' ? 'bg-[#B42318]' :
            analysis.status === 'completed' || analysis.status === 'completed_with_warnings' ? 'bg-[#18794E]' :
            isQueued ? 'bg-[#D97706]' :
            'bg-[#315BE8] animate-pulse'
          }`} />
          <span className="text-xs font-semibold text-[#172033]">
            Truthful Circuit Progress
          </span>
          <span className="text-[11px] font-mono text-[#718096] bg-[#F1F4F9] px-2 py-0.5 rounded border border-[#E1E6EE]">
            {analysis.analysis_id.slice(0, 8)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isQueued && (
            <span className="text-[11px] font-mono text-[#925C08] bg-[#FFF5DE] border border-[#FEEFC6] px-2 py-0.5 rounded-full flex items-center gap-1">
              <Clock className="w-3 h-3" /> Waiting to begin...
            </span>
          )}
          <span className={`text-[11px] font-mono px-2.5 py-0.5 rounded-full border ${
            analysis.status === 'failed'
              ? 'bg-[#FEF0F0] text-[#B42318] border-[#FECDCA]'
              : analysis.status === 'completed' || analysis.status === 'completed_with_warnings'
              ? 'bg-[#EAF7EF] text-[#18794E] border-[#C8ECCF]'
              : 'bg-[#EEF3FF] text-[#2648C7] border-[#C6D8FF]'
          }`}>
            {analysis.stage || analysis.status}
          </span>
        </div>
      </div>

      {/* 5-Stage Circuit */}
      <div className="relative pt-2 pb-1">
        {/* Horizontal base circuit line */}
        <div className="absolute top-[28px] left-[32px] right-[32px] h-[2px] bg-[#E1E6EE] rounded-full" />

        {/* Completed progression fill */}
        {activeIndex >= 0 && (
          <div
            className="absolute top-[28px] left-[32px] h-[2px] bg-[#315BE8] rounded-full transition-all duration-700 ease-out"
            style={{
              width: `${(activeIndex / (FIVE_STAGES.length - 1)) * (100 - 14)}%`,
            }}
          />
        )}
        {(analysis.status === 'completed' || analysis.status === 'completed_with_warnings') && (
          <div className="absolute top-[28px] left-[32px] right-[32px] h-[2px] bg-[#18794E] rounded-full transition-all duration-700 ease-out" />
        )}

        {/* Animated beam travelling along active segment (slow 4s smooth motion) */}
        {activeIndex > 0 && activeIndex < FIVE_STAGES.length && (
          <div
            className="absolute top-[26px] h-[6px] rounded-full overflow-hidden"
            style={{
              left: `${8 + ((activeIndex - 1) / (FIVE_STAGES.length - 1)) * (100 - 16)}%`,
              width: `${(1 / (FIVE_STAGES.length - 1)) * (100 - 16)}%`,
            }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#315BE8] to-transparent animate-beam-slide" />
          </div>
        )}

        {/* Stage Nodes */}
        <div className="relative flex justify-between">
          {FIVE_STAGES.map((stage, i) => {
            const status = stageStatuses[i];
            return (
              <div
                key={stage.id}
                className="flex flex-col items-center w-0 flex-1"
              >
                {/* Node Circle */}
                <div
                  className={`relative z-10 w-11 h-11 rounded-full border-2 flex items-center justify-center transition-all duration-300 ${
                    status === 'active'
                      ? 'bg-[#EEF3FF] border-[#315BE8] text-[#315BE8] ring-4 ring-[#315BE8]/15 shadow-sm'
                      : status === 'completed'
                      ? 'bg-[#315BE8] border-[#315BE8] text-white shadow-xs'
                      : status === 'failed'
                      ? 'bg-[#FEF0F0] border-[#B42318] text-[#B42318]'
                      : status === 'warning'
                      ? 'bg-[#FFF5DE] border-[#B57914] text-[#925C08]'
                      : 'bg-white border-[#E1E6EE] text-[#718096]'
                  }`}
                >
                  {status === 'completed' ? (
                    <CheckCircle2 className="w-5 h-5" />
                  ) : status === 'failed' ? (
                    <XCircle className="w-5 h-5" />
                  ) : status === 'active' ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    stage.icon
                  )}

                  {/* Restrained pulse ring on active node */}
                  {status === 'active' && (
                    <span className="absolute inset-0 rounded-full border border-[#315BE8] animate-ping opacity-25" />
                  )}
                </div>

                {/* Stage Title */}
                <span
                  className={`mt-2.5 text-xs font-semibold leading-tight text-center ${
                    status === 'active'
                      ? 'text-[#315BE8]'
                      : status === 'completed'
                      ? 'text-[#172033]'
                      : status === 'failed'
                      ? 'text-[#B42318]'
                      : 'text-[#718096]'
                  }`}
                >
                  {stage.label}
                </span>

                {/* Stage Subtitle */}
                <span className="text-[10px] text-[#718096] text-center leading-tight mt-0.5">
                  {stage.sublabel}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
