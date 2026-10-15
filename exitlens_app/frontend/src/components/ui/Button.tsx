import React, { forwardRef } from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'subtle';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      icon,
      iconPosition = 'left',
      isLoading = false,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-md border cursor-pointer select-none transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 disabled:pointer-events-none';

    const sizeStyles = {
      sm: 'text-xs px-2.5 py-1.5 gap-1.5 h-8',
      md: 'text-sm px-3.5 py-2 gap-2 h-9',
      lg: 'text-base px-4 py-2.5 gap-2.5 h-11',
    }[size];

    const variantStyles = {
      primary:
        'bg-[#315BE8] hover:bg-[#2648C7] active:bg-[#1E3BB8] text-white border-transparent focus-visible:outline-[#315BE8]',
      secondary:
        'bg-[#EEF1F5] hover:bg-[#E1E6EE] text-[#172033] border-transparent focus-visible:outline-[#315BE8]',
      outline:
        'bg-white hover:bg-[#F5F7FA] text-[#172033] border-[#E1E6EE] hover:border-[#CCD5E2] focus-visible:outline-[#315BE8]',
      subtle:
        'bg-[#EEF3FF] hover:bg-[#E0EAFF] text-[#2648C7] border-transparent focus-visible:outline-[#315BE8]',
      ghost:
        'bg-transparent hover:bg-[#EEF1F5] text-[#526176] hover:text-[#172033] border-transparent focus-visible:outline-[#315BE8]',
    }[variant];

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
        {...props}
      >
        {isLoading && (
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4 text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {!isLoading && icon && iconPosition === 'left' && (
          <span className="shrink-0 flex items-center">{icon}</span>
        )}
        <span>{children}</span>
        {!isLoading && icon && iconPosition === 'right' && (
          <span className="shrink-0 flex items-center">{icon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
