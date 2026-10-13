import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ClipboardList,
  Users,
  CalendarDays,
  Headphones,
  Wrench,
  BrainCircuit,
  Settings as SettingsIcon,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { hasRole } = useAuth();

  const navItems = [
    {
      to: '/',
      label: 'Dispatcher Dashboard',
      icon: <LayoutDashboard className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'DISPATCHER'],
    },
    {
      to: '/work-orders',
      label: 'Work Orders',
      icon: <ClipboardList className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'DISPATCHER', 'TECHNICIAN'],
    },
    {
      to: '/technicians',
      label: 'Technicians',
      icon: <Users className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'DISPATCHER'],
    },
    {
      to: '/dispatch',
      label: 'Dispatch Board',
      icon: <CalendarDays className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'DISPATCHER'],
    },
    {
      to: '/intake',
      label: 'Customer Intake AI',
      icon: <Headphones className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'DISPATCHER', 'CUSTOMER'],
    },
    {
      to: '/technician-portal',
      label: 'Technician View',
      icon: <Wrench className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'TECHNICIAN'],
    },
    {
      to: '/ml',
      label: 'ML Insights',
      icon: <BrainCircuit className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'DISPATCHER'],
    },
    {
      to: '/settings',
      label: 'Settings',
      icon: <SettingsIcon className="w-4 h-4" />,
      allowedRoles: ['ADMIN', 'DISPATCHER'],
    },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed top-16 bottom-0 left-0 z-40 w-64 bg-slate-900 text-slate-300 border-r border-slate-800 flex flex-col transition-transform duration-200 ease-in-out md:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-4 md:hidden flex justify-end border-b border-slate-800">
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider px-3 mb-2">
            Operations & Service
          </div>
          {navItems.map((item) => {
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => onClose()}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`
                }
              >
                <span className="shrink-0">{item.icon}</span>
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </div>

        <div className="p-4 border-t border-slate-800/80">
          <div className="bg-slate-800/50 rounded-xl p-3 border border-slate-700/50">
            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400 mb-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block" />
              Cluster Online
            </div>
            <p className="text-[11px] text-slate-400 leading-snug">
              MongoDB, Redis Outbox & Scikit-learn Pipeline v1.0.0
            </p>
          </div>
        </div>
      </aside>
    </>
  );
};

