import { Menu, WifiOff, CheckCircle2, AlertCircle, RefreshCw, FileText } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { StatusBadge } from '../ui/StatusBadge';
import { useAnalysisContext } from '../../context/useAnalysisContext';

export interface TopBarProps {
  onMenuToggle: () => void;
}

export function TopBar({ onMenuToggle }: TopBarProps) {
  const location = useLocation();
  const { health } = useAnalysisContext();

  const getPageInfo = (path: string) => {
    switch (path) {
      case '/workspace':
        return { section: 'Workbench', title: 'Repository Workspace' };
      case '/analysis':
        return { section: 'Workbench', title: 'Dependency Analysis & Inventory' };
      case '/verification':
        return { section: 'Workbench', title: 'Verification Workbench' };
      case '/capsule':
        return { section: 'Workbench', title: 'Dependency Exit Capsule' };
      default:
        return { section: 'Workbench', title: 'Workspace' };
    }
  };

  const { section, title } = getPageInfo(location.pathname);

  const renderHealthBadge = () => {
    if (health.isLoading) {
      return (
        <StatusBadge variant="neutral" size="sm" dot className="hidden sm:inline-flex">
          Checking Backend...
        </StatusBadge>
      );
    }

    if (health.isBackendAvailable) {
      if (health.isModelAvailable) {
        return (
          <StatusBadge
            variant="success"
            size="sm"
            dot
            icon={<CheckCircle2 className="w-3 h-3" />}
            className="hidden sm:inline-flex"
            title={`Connected to FastAPI. Model: ${health.data?.model?.configured_id || 'Gemma 4'}`}
          >
            Backend & Gemma 4 Ready
          </StatusBadge>
        );
      }

      return (
        <StatusBadge
          variant="warning"
          size="sm"
          dot
          icon={<AlertCircle className="w-3 h-3" />}
          className="hidden sm:inline-flex"
          title="Backend connected, but local Gemma 4 model is not detected or ready"
        >
          Backend Connected · Model Unavailable
        </StatusBadge>
      );
    }

    return (
      <StatusBadge
        variant="neutral"
        size="sm"
        dot
        icon={<WifiOff className="w-3 h-3" />}
        className="hidden sm:inline-flex text-[#B42318] bg-[#FEF0F0] border-[#FECDCA]"
        title={health.error || 'FastAPI server not responding at configured URL'}
      >
        Backend: Unavailable
      </StatusBadge>
    );
  };

  return (
    <header className="h-16 px-4 sm:px-6 bg-white border-b border-[#E1E6EE] flex items-center justify-between shrink-0 select-none">
      <div className="flex items-center gap-3">
        {/* Mobile menu toggle */}
        <button
          type="button"
          onClick={onMenuToggle}
          className="lg:hidden p-2 rounded-md text-[#526176] hover:text-[#172033] hover:bg-[#EEF1F5] transition-colors focus-visible:outline-2 focus-visible:outline-[#315BE8]"
          aria-label="Toggle navigation drawer"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Breadcrumb Context */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-[#718096] font-medium hidden sm:inline">{section}</span>
          <span className="text-[#CCD5E2] hidden sm:inline">/</span>
          <span className="text-[#172033] font-semibold truncate">{title}</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Live backend & model readiness badge */}
        <div className="flex items-center gap-1.5">
          {renderHealthBadge()}
          <button
            type="button"
            onClick={() => health.refetch()}
            className="p-1 rounded text-[#718096] hover:text-[#172033] hover:bg-[#EEF1F5] transition-colors focus-visible:outline-2 focus-visible:outline-[#315BE8]"
            title="Refresh backend status"
            aria-label="Refresh backend status"
          >
            <RefreshCw className={`w-3 h-3 ${health.isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <a
          href="https://github.com/rishrek/LinkWatch"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-[#526176] hover:text-[#172033] rounded-md border border-[#E1E6EE] hover:bg-[#F5F7FA] transition-colors duration-150"
          title="Target repository: LinkWatch"
        >
          <FileText className="w-3.5 h-3.5 text-[#718096]" />
          <span>Target: LinkWatch</span>
        </a>
      </div>
    </header>
  );
}
