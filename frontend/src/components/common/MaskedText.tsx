import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export interface MaskedTextProps {
  value: string;
  type?: 'phone' | 'email' | 'generic';
  className?: string;
}

export const MaskedText: React.FC<MaskedTextProps> = ({
  value,
  type = 'generic',
  className = '',
}) => {
  const [isRevealed, setIsRevealed] = useState(false);

  if (!value) return <span className="text-slate-400 italic">None</span>;

  const maskValue = (str: string): string => {
    if (type === 'phone') {
      // e.g. +14045550183 -> +1 (404) •••-0183
      const cleaned = str.replace(/\s+/g, '');
      if (cleaned.length >= 7) {
        const last4 = cleaned.slice(-4);
        const prefix = cleaned.slice(0, 2);
        return `${prefix} ••• ••• ${last4}`;
      }
      return '••••••' + str.slice(-2);
    }

    if (type === 'email') {
      // e.g. john.doe@example.com -> j•••e@example.com
      const parts = str.split('@');
      if (parts.length === 2) {
        const [user, domain] = parts;
        const visibleUser = user.length > 2 ? `${user[0]}•••${user[user.length - 1]}` : '•••';
        return `${visibleUser}@${domain}`;
      }
    }

    // generic fallback
    if (str.length > 4) {
      return str.slice(0, 2) + '••••' + str.slice(-2);
    }
    return '••••';
  };

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-sm ${className}`}>
      <span>{isRevealed ? value : maskValue(value)}</span>
      <button
        type="button"
        onClick={() => setIsRevealed(!isRevealed)}
        className="text-slate-400 hover:text-slate-600 transition-colors p-0.5 rounded focus:outline-none focus:ring-1 focus:ring-brand-500"
        title={isRevealed ? 'Mask sensitive data' : 'Reveal sensitive data'}
        aria-label={isRevealed ? 'Mask value' : 'Reveal value'}
      >
        {isRevealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
      </button>
    </span>
  );
};

