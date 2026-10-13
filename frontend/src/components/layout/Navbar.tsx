import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Shield, LogOut, Radio, Wrench, Menu } from 'lucide-react';
import { Badge } from '../common/Badge';

export const Navbar: React.FC<{ onToggleSidebar?: () => void }> = ({ onToggleSidebar }) => {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="md:hidden text-slate-500 hover:text-slate-800 p-1.5 rounded-lg hover:bg-slate-100"
            aria-label="Toggle menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-700 to-sky-500 flex items-center justify-center text-white shadow-sm shadow-brand-500/20">
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold text-slate-900 tracking-tight text-lg leading-none block">
              FieldOps <span className="text-brand-600">AI</span>
            </span>
            <span className="text-[10px] text-slate-500 font-semibold tracking-wider uppercase">
              Voice-First Field Service
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {user ? (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-sm font-semibold text-slate-800 leading-tight">{user.full_name}</span>
              <span className="text-xs text-slate-500">{user.email}</span>
            </div>
            <Badge variant="neutral" size="sm" className="bg-slate-100 border-slate-300">
              {user.role}
            </Badge>
            <button
              onClick={logout}
              title="Logout"
              className="text-slate-400 hover:text-rose-600 transition-colors p-2 rounded-lg hover:bg-slate-100"
              aria-label="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="text-xs text-slate-500">Not authenticated</div>
        )}
      </div>
    </header>
  );
};

