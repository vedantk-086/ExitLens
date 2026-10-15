import React from 'react';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  compact?: boolean;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  compact = false,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center rounded-lg border border-dashed border-[#CCD5E2] bg-[#F5F7FA]/60 ${
        compact ? 'p-6 sm:p-8' : 'p-10 sm:p-14'
      } ${className}`}
    >
      {icon && (
        <div className="w-11 h-11 rounded-lg bg-[#EEF1F5] text-[#526176] border border-[#E1E6EE] flex items-center justify-center mb-3 shrink-0">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-[#172033] tracking-tight mb-1">
        {title}
      </h3>
      <p className="text-xs text-[#526176] max-w-md leading-relaxed mb-4">
        {description}
      </p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
