import React from 'react';

export interface PanelProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  padded?: boolean;
}

export function Panel({
  title,
  subtitle,
  actions,
  children,
  footer,
  padded = true,
  className = '',
  ...props
}: PanelProps) {
  const hasHeader = Boolean(title || subtitle || actions);

  return (
    <div
      className={`bg-white rounded-lg border border-[#E1E6EE] shadow-2xs overflow-hidden ${className}`}
      {...props}
    >
      {hasHeader && (
        <div className="px-5 py-4 border-b border-[#E1E6EE] flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white">
          <div className="flex flex-col gap-0.5">
            {title && (
              <h2 className="text-sm font-semibold text-[#172033] tracking-tight m-0">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-xs text-[#526176] m-0 leading-normal">
                {subtitle}
              </p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      <div className={padded ? 'p-5 sm:p-6' : ''}>{children}</div>
      {footer && (
        <div className="px-5 py-3 bg-[#F5F7FA] border-t border-[#E1E6EE] flex items-center justify-between text-xs text-[#526176]">
          {footer}
        </div>
      )}
    </div>
  );
}
