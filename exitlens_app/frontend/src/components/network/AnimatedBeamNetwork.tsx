import React, { useEffect, useRef, useState } from 'react';
import {
  FolderGit2,
  FileText,
  FileCode,
  Cpu,
  Layers,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface BeamNode {
  id: string;
  label: string;
  sublabel: string;
  icon: React.ReactNode;
  x: number;
  y: number;
  side: 'left' | 'center' | 'right';
}

interface BeamPath {
  id: string;
  from: string;
  to: string;
  d: string;
  animated?: boolean;
  delay?: number;
  duration?: number;
}

// ─── AnimatedBeamNetwork ─────────────────────────────────────────────────────

export function AnimatedBeamNetwork({ className = '' }: { className?: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 720, height: 360 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.max(rect.width, 320),
          height: Math.max(rect.height, 280),
        });
      }
    };
    updateSize();
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      const ro = new ResizeObserver(updateSize);
      ro.observe(containerRef.current);
      return () => ro.disconnect();
    }
  }, []);

  const w = dimensions.width;
  const h = dimensions.height;

  // Node positions — responsive percentage-based
  const padX = w < 500 ? 16 : 40;
  const centerX = w / 2;
  const leftX = padX + 48;
  const rightX = w - padX - 48;
  const topY = h * 0.15;
  const midY = h * 0.5;
  const botY = h * 0.85;

  const nodes: BeamNode[] = [
    {
      id: 'git-repo',
      label: 'Git Repository',
      sublabel: 'Local / HTTPS clone',
      icon: <FolderGit2 className="w-4 h-4" />,
      x: leftX,
      y: topY,
      side: 'left',
    },
    {
      id: 'manifests',
      label: 'Manifests & Lockfiles',
      sublabel: 'requirements · pyproject',
      icon: <FileText className="w-4 h-4" />,
      x: leftX,
      y: midY,
      side: 'left',
    },
    {
      id: 'source',
      label: 'Source & Tests',
      sublabel: 'AST import traces',
      icon: <FileCode className="w-4 h-4" />,
      x: leftX,
      y: botY,
      side: 'left',
    },
    {
      id: 'core',
      label: 'ExitLens Core',
      sublabel: 'Gemma 4 + Rules Engine',
      icon: <Cpu className="w-5 h-5" />,
      x: centerX,
      y: midY,
      side: 'center',
    },
    {
      id: 'risk-map',
      label: 'Usage & Risk Map',
      sublabel: 'Evidence-linked findings',
      icon: <Layers className="w-4 h-4" />,
      x: rightX,
      y: topY,
      side: 'right',
    },
    {
      id: 'migration',
      label: 'Migration Plan',
      sublabel: 'Gemma 4 proposals',
      icon: <Sparkles className="w-4 h-4" />,
      x: rightX,
      y: midY,
      side: 'right',
    },
    {
      id: 'capsule',
      label: 'Exit Capsule',
      sublabel: 'Canonical JSON & MD',
      icon: <ShieldCheck className="w-4 h-4" />,
      x: rightX,
      y: botY,
      side: 'right',
    },
  ];

  // Core junction points
  const coreLeftJunction = centerX - 52;
  const coreRightJunction = centerX + 52;

  // Paths with right-angle circuit traces
  const paths: BeamPath[] = [
    {
      id: 'git-to-core',
      from: 'git-repo',
      to: 'core',
      d: `M ${leftX + 56} ${topY} L ${coreLeftJunction - 20} ${topY} L ${coreLeftJunction - 20} ${midY} L ${coreLeftJunction} ${midY}`,
      animated: true,
      delay: 0,
      duration: 4,
    },
    {
      id: 'manifest-to-core',
      from: 'manifests',
      to: 'core',
      d: `M ${leftX + 56} ${midY} L ${coreLeftJunction} ${midY}`,
      animated: true,
      delay: 1.5,
      duration: 3,
    },
    {
      id: 'source-to-core',
      from: 'source',
      to: 'core',
      d: `M ${leftX + 56} ${botY} L ${coreLeftJunction - 20} ${botY} L ${coreLeftJunction - 20} ${midY} L ${coreLeftJunction} ${midY}`,
      animated: true,
      delay: 3,
      duration: 4,
    },
    {
      id: 'core-to-risk',
      from: 'core',
      to: 'risk-map',
      d: `M ${coreRightJunction} ${midY} L ${coreRightJunction + 20} ${midY} L ${coreRightJunction + 20} ${topY} L ${rightX - 56} ${topY}`,
      animated: true,
      delay: 5,
      duration: 4,
    },
    {
      id: 'core-to-migration',
      from: 'core',
      to: 'migration',
      d: `M ${coreRightJunction} ${midY} L ${rightX - 56} ${midY}`,
      animated: true,
      delay: 6.5,
      duration: 3,
    },
    {
      id: 'core-to-capsule',
      from: 'core',
      to: 'capsule',
      d: `M ${coreRightJunction} ${midY} L ${coreRightJunction + 20} ${midY} L ${coreRightJunction + 20} ${botY} L ${rightX - 56} ${botY}`,
      animated: true,
      delay: 8,
      duration: 4,
    },
  ];

  return (
    <div
      ref={containerRef}
      className={`relative w-full aspect-[2/1] min-h-[280px] max-h-[420px] ${className}`}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${w} ${h}`}
        className="w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="ExitLens dependency analysis architecture diagram"
      >
        <defs>
          {/* Dot grid pattern */}
          <pattern id="hero-dot-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="12" cy="12" r="0.8" fill="#DCE4F0" />
          </pattern>

          {/* Beam gradient */}
          <linearGradient id="beam-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#315BE8" stopOpacity="0" />
            <stop offset="40%" stopColor="#315BE8" stopOpacity="0.8" />
            <stop offset="60%" stopColor="#7BA4FF" stopOpacity="1" />
            <stop offset="100%" stopColor="#315BE8" stopOpacity="0" />
          </linearGradient>

          {/* Core glow filter */}
          <filter id="core-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background dot grid */}
        <rect width="100%" height="100%" fill="url(#hero-dot-grid)" opacity="0.5" />

        {/* Circuit trace paths (background) */}
        {paths.map((path) => (
          <path
            key={`bg-${path.id}`}
            d={path.d}
            fill="none"
            stroke="#DCE4F0"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* Animated beam signals */}
        {paths
          .filter((p) => p.animated)
          .map((path) => (
            <g key={`beam-${path.id}`}>
              {/* Glowing beam dot */}
              <circle r="4" fill="#315BE8" opacity="0.9">
                <animateMotion
                  dur={`${path.duration || 4}s`}
                  begin={`${path.delay || 0}s`}
                  repeatCount="indefinite"
                  path={path.d}
                  fill="freeze"
                />
                <animate
                  attributeName="opacity"
                  values="0;0.9;0.9;0"
                  keyTimes="0;0.05;0.9;1"
                  dur={`${path.duration || 4}s`}
                  begin={`${path.delay || 0}s`}
                  repeatCount="indefinite"
                />
              </circle>
              {/* Outer glow */}
              <circle r="8" fill="#315BE8" opacity="0.15">
                <animateMotion
                  dur={`${path.duration || 4}s`}
                  begin={`${path.delay || 0}s`}
                  repeatCount="indefinite"
                  path={path.d}
                  fill="freeze"
                />
                <animate
                  attributeName="opacity"
                  values="0;0.15;0.15;0"
                  keyTimes="0;0.05;0.9;1"
                  dur={`${path.duration || 4}s`}
                  begin={`${path.delay || 0}s`}
                  repeatCount="indefinite"
                />
              </circle>
            </g>
          ))}

        {/* Junction dots at bends */}
        <circle cx={coreLeftJunction - 20} cy={topY} r="2.5" fill="#C6D8FF" stroke="#E1E6EE" strokeWidth="1" />
        <circle cx={coreLeftJunction - 20} cy={botY} r="2.5" fill="#C6D8FF" stroke="#E1E6EE" strokeWidth="1" />
        <circle cx={coreRightJunction + 20} cy={topY} r="2.5" fill="#C6D8FF" stroke="#E1E6EE" strokeWidth="1" />
        <circle cx={coreRightJunction + 20} cy={botY} r="2.5" fill="#C6D8FF" stroke="#E1E6EE" strokeWidth="1" />

        {/* Node connector dots on the core */}
        <circle cx={coreLeftJunction} cy={midY} r="3" fill="#315BE8" />
        <circle cx={coreRightJunction} cy={midY} r="3" fill="#315BE8" />
      </svg>

      {/* HTML-overlay nodes for crisp text rendering */}
      {nodes.map((node) => {
        const isCenter = node.side === 'center';
        const nodeW = isCenter ? 112 : 112;

        return (
          <div
            key={node.id}
            className="absolute flex flex-col items-center gap-1"
            style={{
              left: `${(node.x / w) * 100}%`,
              top: `${(node.y / h) * 100}%`,
              transform: 'translate(-50%, -50%)',
              width: `${nodeW}px`,
            }}
          >
            <div
              className={`flex flex-col items-center gap-1 rounded-lg border px-3 py-2 transition-all duration-300 ${
                isCenter
                  ? 'bg-[#315BE8] text-white border-[#2648C7] shadow-md shadow-[#315BE8]/20 py-3'
                  : 'bg-white text-[#172033] border-[#E1E6EE] shadow-xs hover:border-[#C6D8FF] hover:shadow-sm'
              }`}
            >
              <div
                className={`flex items-center justify-center rounded-md ${
                  isCenter
                    ? 'w-8 h-8 bg-white/20'
                    : 'w-7 h-7 bg-[#EEF3FF] border border-[#C6D8FF]'
                }`}
              >
                <span className={isCenter ? 'text-white' : 'text-[#315BE8]'}>
                  {node.icon}
                </span>
              </div>
              <span
                className={`text-[10px] font-semibold leading-tight text-center ${
                  isCenter ? 'text-white' : 'text-[#172033]'
                }`}
              >
                {node.label}
              </span>
              <span
                className={`text-[9px] leading-tight text-center font-mono ${
                  isCenter ? 'text-white/70' : 'text-[#718096]'
                }`}
              >
                {node.sublabel}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
