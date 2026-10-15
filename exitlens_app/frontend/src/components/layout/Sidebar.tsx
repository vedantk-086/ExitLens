import {
  FolderGit2,
  SearchCode,
  ShieldCheck,
  PackageCheck,
  Cpu,
} from 'lucide-react';
import { NavigationItem } from './NavigationItem';

export interface SidebarProps {
  onNavClick?: () => void;
  className?: string;
}

export function Sidebar({ onNavClick, className = '' }: SidebarProps) {
  const navItems = [
    {
      to: '/workspace',
      label: 'Workspace',
      icon: <FolderGit2 className="w-4.5 h-4.5" />,
    },
    {
      to: '/analysis',
      label: 'Analysis',
      icon: <SearchCode className="w-4.5 h-4.5" />,
    },
    {
      to: '/verification',
      label: 'Verification',
      icon: <ShieldCheck className="w-4.5 h-4.5" />,
    },
    {
      to: '/capsule',
      label: 'Capsule',
      icon: <PackageCheck className="w-4.5 h-4.5" />,
    },
  ];

  return (
    <aside
      className={`w-60 h-full flex flex-col bg-white border-r border-[#E1E6EE] select-none ${className}`}
    >
      {/* Brand Header */}
      <div className="h-16 px-5 flex items-center gap-3 border-b border-[#E1E6EE] shrink-0">
        <div className="w-8 h-8 rounded-md bg-[#EEF3FF] border border-[#C6D8FF] flex items-center justify-center text-[#315BE8] shrink-0">
          <svg
            className="w-4.5 h-4.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </div>
        <div className="flex flex-col">
          <span className="text-base font-bold text-[#172033] tracking-tight leading-none">
            ExitLens
          </span>
          <span className="text-[9px] font-semibold text-[#718096] tracking-wider uppercase mt-1 leading-none">
            Dependency Intelligence
          </span>
        </div>
      </div>

      {/* Primary Navigation */}
      <div className="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
        <div className="px-2 pb-2 text-[10px] font-semibold tracking-wider text-[#718096] uppercase">
          Workbench
        </div>
        {navItems.map((item) => (
          <NavigationItem
            key={item.to}
            to={item.to}
            label={item.label}
            icon={item.icon}
            onClick={onNavClick}
          />
        ))}
      </div>

      {/* Sidebar Footer */}
      <div className="p-4 border-t border-[#E1E6EE] bg-[#F5F7FA]/70 flex flex-col gap-2 shrink-0">
        <div className="flex items-center gap-2 text-xs text-[#526176]">
          <Cpu className="w-3.5 h-3.5 text-[#718096] shrink-0" />
          <span className="font-medium text-[#172033]">Local-first analysis</span>
        </div>
        <div className="text-[11px] text-[#718096] leading-tight">
          Gemma 4 · Dependency resilience
        </div>
        <div className="pt-2 border-t border-[#E1E6EE]/70 flex items-center justify-between text-[11px]">
          <span className="text-[#718096]">Architecture:</span>
          <span className="font-mono text-[#526176]">Step 1 (Shell)</span>
        </div>
      </div>
    </aside>
  );
}
