import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingSpinner: React.FC<{ message?: string; size?: 'sm' | 'md' | 'lg' }> = ({
  message = 'Loading...',
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className="flex flex-col items-center justify-center p-8 text-center" role="status">
      <Loader2 className={`${sizeClasses[size]} animate-spin text-brand-600 mb-2`} />
      <span className="text-sm font-medium text-slate-500">{message}</span>
    </div>
  );
};

