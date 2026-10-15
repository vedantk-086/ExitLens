import React from 'react';

export type StatusVariant =
  | 'neutral'
  | 'info'
  | 'warning'
  | 'failure'
  | 'success';

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode;
  variant?: StatusVariant;
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
  className?: string;
  dot?: boolean;
}

export function StatusBadge({
  children,
  variant = 'neutral',
  size = 'md',
  icon,
  className = '',
  dot = false,
  ...props
}: StatusBadgeProps) {
  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5 gap-1.5',
    md: 'text-xs px-2.5 py-1 gap-1.5 font-medium',
  }[size];

  const variantStyles: Record<StatusVariant, { badge: string; dotColor: string }> = {
    neutral: {
      badge: 'bg-[#EEF1F5] text-[#526176] border-[#E1E6EE]',
      dotColor: 'bg-[#718096]',
    },
    info: {
      badge: 'bg-[#EEF3FF] text-[#2648C7] border-[#C6D8FF]',
      dotColor: 'bg-[#315BE8]',
    },
    warning: {
      badge: 'bg-[#FFF5DE] text-[#925C08] border-[#FDE4A4]',
      dotColor: 'bg-[#B57914]',
    },
    failure: {
      badge: 'bg-[#FEF0F0] text-[#B42318] border-[#FECDCA]',
      dotColor: 'bg-[#D92D20]',
    },
    success: {
      badge: 'bg-[#EAF7EF] text-[#18794E] border-[#C8ECCF]',
      dotColor: 'bg-[#18794E]',
    },
  };

  const { badge, dotColor } = variantStyles[variant];

  return (
    <span
      className={`inline-flex items-center rounded-full border tracking-normal select-none ${badge} ${sizeStyles} ${className}`}
      {...props}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />}
      {icon && <span className="shrink-0 flex items-center">{icon}</span>}
      <span>{children}</span>
    </span>
  );
}
