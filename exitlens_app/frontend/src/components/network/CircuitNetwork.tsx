import React from 'react';
import {
  FolderGit2,
  FileCode,
  FileText,
  Cpu,
  Layers,
  ShieldCheck,
  CheckCircle2,
  Activity,
  AlertCircle,
  Clock,
  Sparkles,
  Check,
} from 'lucide-react';
import { AnalysisStatusResponse } from '../../types/api';

// ─── Types & Props ────────────────────────────────────────────────────────────

export interface CircuitNetworkProps {
  mode?: 'hero' | 'live';
  activeAnalysis?: AnalysisStatusResponse | null;
  className?: string;
  onNodeClick?: (nodeId: string) => void;
}

interface WorkflowNode {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  category: 'input' | 'core' | 'output';
  status?: 'pending' | 'active' | 'completed' | 'failed' | 'warning';
}

// ─── CircuitNetwork Component ─────────────────────────────────────────────────

export function CircuitNetwork({
  mode = 'hero',
  activeAnalysis,
  className = '',
  onNodeClick,
}: CircuitNetworkProps) {
  // If in live mode, calculate node statuses from activeAnalysis
  const isLive = mode === 'live';
  const stage = activeAnalysis?.stage || '';
  const runStatus = activeAnalysis?.status;

  const getLiveStageStatus = (stageName: string): 'pending' | 'active' | 'completed' | 'failed' | 'warning' => {
    if (!activeAnalysis) return 'pending';
    if (runStatus === 'failed') {
      if (stage === stageName) return 'failed';
    }

    const stagesOrder = [
      'validating_repository',
      'scanning',
      'mapping_usage',
      'assessing_risk',
      'generating_recommendations',
      'ready_for_verification',
      'verifying',
      'completed',
    ];

    const currentIdx = stagesOrder.indexOf(stage);
    const targetIdx = stagesOrder.indexOf(stageName);

    if (runStatus === 'completed' || runStatus === 'completed_with_warnings') {
      return runStatus === 'completed_with_warnings' && stageName === 'generating_recommendations'
        ? 'warning'
        : 'completed';
    }

    if (currentIdx === -1) return 'pending';
    if (currentIdx === targetIdx) return 'active';
    if (currentIdx > targetIdx) return 'completed';
    return 'pending';
  };

  // Define nodes
  const inputNodes: WorkflowNode[] = [
    {
      id: 'git-repo',
      title: 'Git Repository',
      subtitle: isLive ? activeAnalysis?.repository?.value || 'Target repository' : 'Local path or HTTPS clone',
      icon: <FolderGit2 className="w-4 h-4 text-[#315BE8]" />,
      category: 'input',
      status: isLive ? getLiveStageStatus('validating_repository') : 'completed',
    },
    {
      id: 'manifests',
      title: 'Manifests & Lockfiles',
      subtitle: isLive ? 'requirements.txt, pyproject' : 'AST & static declarations',
      icon: <FileText className="w-4 h-4 text-[#315BE8]" />,
      category: 'input',
      status: isLive ? getLiveStageStatus('scanning') : 'completed',
    },
    {
      id: 'source-tests',
      title: 'Source & Tests',
      subtitle: isLive ? 'Import mappings & call-sites' : 'Usage traces & AST links',
      icon: <FileCode className="w-4 h-4 text-[#315BE8]" />,
      category: 'input',
      status: isLive ? getLiveStageStatus('mapping_usage') : 'completed',
    },
  ];

  const coreNode: WorkflowNode = {
    id: 'core',
    title: 'ExitLens Analysis Core',
    subtitle: isLive
      ? runStatus === 'generating_recommendations'
        ? 'Gemma 4 synthesizing plan...'
        : runStatus === 'completed'
        ? 'Analysis complete'
        : 'Transparent risk engine'
      : 'Deterministic rules & local Gemma 4',
    icon: <Cpu className="w-5 h-5 text-white" />,
    category: 'core',
    status: isLive ? getLiveStageStatus('assessing_risk') : 'active',
  };

  const outputNodes: WorkflowNode[] = [
    {
      id: 'usage-risk',
      title: 'Usage Map & Risk Evidence',
      subtitle: isLive
        ? `${activeAnalysis?.summary?.dependencies_flagged ?? 0} flagged dependencies`
        : 'Observed AST call-sites & rule ledger',
      icon: <Layers className="w-4 h-4 text-[#315BE8]" />,
      category: 'output',
      status: isLive ? getLiveStageStatus('assessing_risk') : 'completed',
    },
    {
      id: 'gemma-migration',
      title: 'Gemma 4 Migration Plan',
      subtitle: isLive
        ? `${activeAnalysis?.summary?.recommendations_available ?? 0} plans available`
        : 'Structured candidate steps & API diffs',
      icon: <Sparkles className="w-4 h-4 text-[#315BE8]" />,
      category: 'output',
      status: isLive ? getLiveStageStatus('generating_recommendations') : 'completed',
    },
    {
      id: 'capsule',
      title: 'Verification & Exit Capsule',
      subtitle: isLive
        ? activeAnalysis?.artifacts?.capsule_json
          ? 'Canonical capsule ready'
          : 'Ready for verification'
        : 'Dual JSON/MD & verified outcomes',
      icon: <ShieldCheck className="w-4 h-4 text-[#315BE8]" />,
      category: 'output',
      status: isLive
        ? activeAnalysis?.artifacts?.capsule_json
          ? 'completed'
          : getLiveStageStatus('ready_for_verification')
        : 'completed',
    },
  ];

  // Status visual styles
  const getNodeBorder = (status?: string) => {
    switch (status) {
      case 'active':
        return 'border-[#315BE8] ring-2 ring-[#315BE8]/20 bg-white shadow-sm';
      case 'completed':
        return 'border-[#C8ECCF] bg-[#FAFDFB]';
      case 'failed':
        return 'border-[#FECDCA] bg-[#FEF0F0]';
      case 'warning':
        return 'border-[#FDE4A4] bg-[#FFF5DE]';
      default:
        return 'border-[#E1E6EE] bg-white';
    }
  };

  return (
    <div
      className={`relative rounded-xl border border-[#E1E6EE] bg-[#F8FAFC] p-4 lg:p-6 overflow-hidden select-none ${className}`}
    >
      {/* Background Circuit Grid Pattern */}
      <svg
        className="absolute inset-0 w-full h-full opacity-40 pointer-events-none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <pattern id="circuit-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path
              d="M 32 0 L 0 0 0 32"
              fill="none"
              stroke="#DCE4F0"
              strokeWidth="0.75"
              strokeDasharray="1 3"
            />
            <circle cx="0" cy="0" r="1" fill="#C6D8FF" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#circuit-grid)" />
      </svg>

      {/* Header bar within circuit card */}
      <div className="relative z-10 flex items-center justify-between pb-4 mb-4 border-b border-[#E1E6EE] text-xs">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#315BE8] animate-pulse" />
          <span className="font-semibold text-[#172033]">
            {isLive ? 'Live Analysis Circuit' : 'Dependency Resilience Architecture'}
          </span>
          <span className="text-[#718096] text-[11px] font-mono">
            {isLive ? `run:${runStatus || 'idle'}` : 'local-first · gemma-4'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-[#526176] font-mono">
          <span className="px-1.5 py-0.5 rounded bg-[#EEF3FF] text-[#2648C7] border border-[#C6D8FF]">
            3 Inputs
          </span>
          <span>→</span>
          <span className="px-1.5 py-0.5 rounded bg-[#315BE8] text-white">
            Core
          </span>
          <span>→</span>
          <span className="px-1.5 py-0.5 rounded bg-[#EAF7EF] text-[#18794E] border border-[#C8ECCF]">
            3 Outputs
          </span>
        </div>
      </div>

      {/* Main Diagram Area */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-7 gap-4 items-center min-h-[300px]">
        {/* Left Inputs (Col 1-2) */}
        <div className="lg:col-span-2 flex flex-col gap-3">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#718096] mb-0.5 flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-[#718096]" />
            Evidence Sources
          </div>
          {inputNodes.map((node) => (
            <div
              key={node.id}
              onClick={() => onNodeClick?.(node.id)}
              className={`p-3 rounded-lg border transition-all duration-150 flex items-start gap-3 relative ${getNodeBorder(
                node.status
              )}`}
            >
              <div className="w-7 h-7 rounded-md bg-[#EEF3FF] border border-[#C6D8FF] flex items-center justify-center shrink-0 mt-0.5">
                {node.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-[#172033] truncate block">
                    {node.title}
                  </span>
                  {node.status === 'completed' && (
                    <Check className="w-3.5 h-3.5 text-[#18794E] shrink-0" />
                  )}
                  {node.status === 'active' && (
                    <Activity className="w-3.5 h-3.5 text-[#315BE8] animate-spin shrink-0" />
                  )}
                </div>
                <span className="text-[11px] text-[#526176] truncate block leading-tight">
                  {node.subtitle}
                </span>
              </div>

              {/* Right connector point */}
              <div className="hidden lg:block absolute -right-1.5 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-[#315BE8] border-2 border-white shadow-xs" />
            </div>
          ))}
        </div>

        {/* Center SVG Circuit Trace (Col 3) - Desktop Only */}
        <div className="hidden lg:flex lg:col-span-1 justify-center items-center h-full relative">
          <svg className="w-full h-full absolute inset-0 overflow-visible" xmlns="http://www.w3.org/2000/svg">
            {/* Track 1: Top to Core */}
            <path
              d="M 0 60 L 50 60 L 50 150 L 100 150"
              fill="none"
              stroke="#C6D8FF"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* Track 2: Mid to Core */}
            <path
              d="M 0 150 L 100 150"
              fill="none"
              stroke="#315BE8"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* Track 3: Bot to Core */}
            <path
              d="M 0 240 L 50 240 L 50 150 L 100 150"
              fill="none"
              stroke="#C6D8FF"
              strokeWidth="2"
              strokeLinecap="round"
            />

            {/* Animated Signal Pulse on Center Track */}
            <circle cx="50" cy="150" r="3.5" fill="#315BE8">
              <animate
                attributeName="cx"
                values="0; 100"
                dur="2s"
                repeatCount="indefinite"
              />
            </circle>
          </svg>
        </div>

        {/* Center Core Node (Col 4) */}
        <div className="lg:col-span-1 flex flex-col items-center justify-center my-2 lg:my-0">
          <div
            onClick={() => onNodeClick?.(coreNode.id)}
            className={`w-full lg:w-36 p-4 rounded-xl border-2 flex flex-col items-center text-center gap-2 relative bg-white shadow-md transition-all duration-200 ${
              coreNode.status === 'active'
                ? 'border-[#315BE8] ring-4 ring-[#315BE8]/10'
                : 'border-[#315BE8]'
            }`}
          >
            {/* Left and Right connector sockets */}
            <div className="hidden lg:block absolute -left-2 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#172033] border-2 border-white" />
            <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#172033] border-2 border-white" />

            <div className="w-12 h-12 rounded-xl bg-[#315BE8] flex items-center justify-center shadow-xs">
              {coreNode.icon}
            </div>

            <div className="flex flex-col gap-0.5">
              <span className="font-bold text-xs text-[#172033] leading-tight">
                {coreNode.title}
              </span>
              <span className="text-[10px] text-[#526176] font-mono leading-tight">
                {coreNode.subtitle}
              </span>
            </div>

            <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-medium uppercase bg-[#EEF3FF] text-[#2648C7] border border-[#C6D8FF]">
              Gemma 4 Core
            </span>
          </div>
        </div>

        {/* Right SVG Circuit Trace (Col 5) - Desktop Only */}
        <div className="hidden lg:flex lg:col-span-1 justify-center items-center h-full relative">
          <svg className="w-full h-full absolute inset-0 overflow-visible" xmlns="http://www.w3.org/2000/svg">
            {/* Track Core to Output 1 */}
            <path
              d="M 0 150 L 50 150 L 50 60 L 100 60"
              fill="none"
              stroke="#C6D8FF"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* Track Core to Output 2 */}
            <path
              d="M 0 150 L 100 150"
              fill="none"
              stroke="#315BE8"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* Track Core to Output 3 */}
            <path
              d="M 0 150 L 50 150 L 50 240 L 100 240"
              fill="none"
              stroke="#C6D8FF"
              strokeWidth="2"
              strokeLinecap="round"
            />

            {/* Animated Signal Pulse on Output 2 Track */}
            <circle cx="50" cy="150" r="3.5" fill="#315BE8">
              <animate
                attributeName="cx"
                values="0; 100"
                dur="2.2s"
                repeatCount="indefinite"
              />
            </circle>
          </svg>
        </div>

        {/* Right Outputs (Col 6-7) */}
        <div className="lg:col-span-2 flex flex-col gap-3">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#718096] mb-0.5 flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-[#18794E]" />
            Generated Artifacts
          </div>
          {outputNodes.map((node) => (
            <div
              key={node.id}
              onClick={() => onNodeClick?.(node.id)}
              className={`p-3 rounded-lg border transition-all duration-150 flex items-start gap-3 relative ${getNodeBorder(
                node.status
              )}`}
            >
              {/* Left connector point */}
              <div className="hidden lg:block absolute -left-1.5 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-[#18794E] border-2 border-white shadow-xs" />

              <div className="w-7 h-7 rounded-md bg-[#EAF7EF] border border-[#C8ECCF] flex items-center justify-center shrink-0 mt-0.5">
                {node.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-[#172033] truncate block">
                    {node.title}
                  </span>
                  {node.status === 'completed' && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#18794E] shrink-0" />
                  )}
                  {node.status === 'active' && (
                    <Activity className="w-3.5 h-3.5 text-[#315BE8] animate-spin shrink-0" />
                  )}
                  {node.status === 'warning' && (
                    <Clock className="w-3.5 h-3.5 text-[#925C08] shrink-0" />
                  )}
                  {node.status === 'failed' && (
                    <AlertCircle className="w-3.5 h-3.5 text-[#B42318] shrink-0" />
                  )}
                </div>
                <span className="text-[11px] text-[#526176] truncate block leading-tight">
                  {node.subtitle}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
