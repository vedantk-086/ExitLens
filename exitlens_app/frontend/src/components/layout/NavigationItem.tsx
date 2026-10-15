import React from 'react';
import { NavLink } from 'react-router-dom';

export interface NavigationItemProps {
  to: string;
  label: string;
  icon: React.ReactNode;
  badge?: React.ReactNode;
  onClick?: () => void;
}

export function NavigationItem({
  to,
  label,
  icon,
  badge,
  onClick,
}: NavigationItemProps) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        `flex items-center justify-between w-full h-10 px-3.5 rounded-md text-sm font-medium transition-colors duration-150 select-none group ${
          isActive
            ? 'bg-[#EEF3FF] text-[#2648C7]'
            : 'text-[#526176] hover:text-[#172033] hover:bg-[#F5F7FA]'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <div className="flex items-center gap-3">
            <span
              className={`shrink-0 transition-colors duration-150 ${
                isActive
                  ? 'text-[#315BE8]'
                  : 'text-[#718096] group-hover:text-[#172033]'
              }`}
            >
              {icon}
            </span>
            <span>{label}</span>
          </div>
          {badge && <div className="shrink-0">{badge}</div>}
        </>
      )}
    </NavLink>
  );
}
