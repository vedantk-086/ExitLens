import React from 'react';

export interface SegmentOption<T extends string = string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface SegmentedControlProps<T extends string = string> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  name?: string;
  className?: string;
  size?: 'sm' | 'md';
}

export function SegmentedControl<T extends string = string>({
  options,
  value,
  onChange,
  name,
  className = '',
  size = 'md',
}: SegmentedControlProps<T>) {
  const containerSize = size === 'sm' ? 'p-0.5' : 'p-1';
  const itemPadding = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-xs font-medium';

  return (
    <div
      role="radiogroup"
      aria-label={name}
      className={`inline-flex rounded-lg bg-[#EEF1F5] border border-[#E1E6EE] ${containerSize} ${className}`}
    >
      {options.map((opt) => {
        const isSelected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            disabled={opt.disabled}
            onClick={() => onChange(opt.value)}
            className={`flex items-center justify-center gap-1.5 rounded-md transition-all duration-150 select-none ${itemPadding} ${
              isSelected
                ? 'bg-white text-[#172033] shadow-xs font-semibold'
                : 'text-[#526176] hover:text-[#172033] hover:bg-white/60'
            } ${opt.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            {opt.icon && (
              <span
                className={`shrink-0 ${
                  isSelected ? 'text-[#315BE8]' : 'text-[#718096]'
                }`}
              >
                {opt.icon}
              </span>
            )}
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
