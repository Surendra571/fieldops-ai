import React from 'react';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'priority' | 'status' | 'category' | 'neutral' | 'success' | 'warning' | 'danger';
  value?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  value,
  size = 'md',
  className = '',
}) => {
  const normalizedValue = (value || children?.toString() || '').toUpperCase();

  const getStyle = (): string => {
    // Priority specific
    if (variant === 'priority' || ['EMERGENCY', 'HIGH', 'MEDIUM', 'ROUTINE'].includes(normalizedValue)) {
      switch (normalizedValue) {
        case 'EMERGENCY':
          return 'bg-rose-100 text-rose-800 border-rose-300 font-bold animate-pulse';
        case 'HIGH':
          return 'bg-orange-100 text-orange-800 border-orange-300 font-semibold';
        case 'MEDIUM':
          return 'bg-amber-100 text-amber-800 border-amber-300';
        case 'ROUTINE':
          return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      }
    }

    // Status specific
    if (variant === 'status' || ['SUBMITTED', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'FAILED', 'TRIAGED'].includes(normalizedValue)) {
      switch (normalizedValue) {
        case 'SUBMITTED':
          return 'bg-sky-100 text-sky-800 border-sky-300';
        case 'TRIAGED':
          return 'bg-indigo-100 text-indigo-800 border-indigo-300';
        case 'SCHEDULED':
        case 'CONFIRMED':
          return 'bg-blue-100 text-blue-800 border-blue-300';
        case 'IN_PROGRESS':
        case 'ON_SITE':
        case 'EN_ROUTE':
          return 'bg-amber-100 text-amber-800 border-amber-300';
        case 'COMPLETED':
          return 'bg-emerald-100 text-emerald-800 border-emerald-300';
        case 'CANCELLED':
        case 'FAILED':
        case 'NO_SHOW':
          return 'bg-rose-100 text-rose-800 border-rose-300';
      }
    }

    // Category specific
    if (variant === 'category') {
      return 'bg-slate-100 text-slate-800 border-slate-300 font-medium';
    }

    // Semantic variants
    switch (variant) {
      case 'success':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'warning':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'danger':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'neutral':
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-xs px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium uppercase tracking-wider ${sizeClasses} ${getStyle()} ${className}`}
    >
      {children}
    </span>
  );
};

