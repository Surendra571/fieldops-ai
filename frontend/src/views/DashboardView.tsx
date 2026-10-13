import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getWorkOrders } from '../api/workOrders';
import { getAppointments } from '../api/appointments';
import { getOutboxMetrics } from '../api/integrations';
import { WorkOrder } from '../types/workOrder';
import { Appointment } from '../types/appointment';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';
import {
  AlertTriangle,
  Calendar,
  Clock,
  ArrowRight,
  Send,
  Zap,
  Activity,
  Layers,
} from 'lucide-react';

export const DashboardView: React.FC = () => {
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [outboxMetrics, setOutboxMetrics] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [woRes, apptRes, metricsRes] = await Promise.all([
        getWorkOrders({ limit: 50 }),
        getAppointments({ limit: 50 }),
        getOutboxMetrics().catch(() => null),
      ]);
      setWorkOrders(Array.isArray(woRes) ? woRes : ((woRes as any)?.items || []));
      setAppointments(Array.isArray(apptRes) ? apptRes : ((apptRes as any)?.items || []));
      setOutboxMetrics(metricsRes);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch operational dashboard metrics.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  if (isLoading) {
    return <LoadingSpinner message="Aggregating operational field metrics..." />;
  }

  if (error) {
    return (
      <ErrorBanner
        title="Dashboard Offline"
        message={error}
        onRetry={loadDashboardData}
      />
    );
  }

  // Defensive array checks
  const safeWorkOrders = Array.isArray(workOrders) ? workOrders : [];
  const safeAppointments = Array.isArray(appointments) ? appointments : [];

  // Derived metrics
  const urgentOrders = safeWorkOrders.filter(
    (wo) => wo.priority === 'EMERGENCY' || wo.priority === 'HIGH'
  );
  const unassignedOrders = safeWorkOrders.filter(
    (wo) => !wo.assigned_technician_id && wo.status !== 'COMPLETED' && wo.status !== 'CANCELLED'
  );
  const openOrders = safeWorkOrders.filter(
    (wo) => wo.status !== 'COMPLETED' && wo.status !== 'CANCELLED'
  );

  const todayStr = new Date().toISOString().split('T')[0];
  const todayAppointments = safeAppointments.filter((a) =>
    a.scheduled_start ? a.scheduled_start.startsWith(todayStr) : false
  );

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Dispatcher Command Center</h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time field operations, SLA tracking, and technician dispatch overview.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/intake">
            <Button variant="outline" size="sm" leftIcon={<Zap className="w-4 h-4 text-amber-500" />}>
              Customer Intake AI
            </Button>
          </Link>
          <Link to="/dispatch">
            <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-4 h-4" />}>
              Match & Dispatch
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Operational Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-l-4 border-l-brand-600">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Open Work Orders</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">{openOrders.length}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center text-brand-600">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3 flex items-center gap-1">
            <span className="font-semibold text-slate-700">{unassignedOrders.length}</span> awaiting technician assignment
          </p>
        </Card>

        <Card className="border-l-4 border-l-rose-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Urgent Requests</p>
              <h3 className="text-2xl font-bold text-rose-600 mt-1">{urgentOrders.length}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-rose-50 flex items-center justify-center text-rose-600">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Emergency & High priority SLA windows
          </p>
        </Card>

        <Card className="border-l-4 border-l-emerald-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Today's Appointments</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">{todayAppointments.length}</h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600">
              <Calendar className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            {appointments.length} total scheduled bookings
          </p>
        </Card>

        <Card className="border-l-4 border-l-indigo-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Outbox Deliveries</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {outboxMetrics ? outboxMetrics.delivered_count : '—'}
              </h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
              <Send className="w-5 h-5" />
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-emerald-500" />
            Transactional notification engine
          </p>
        </Card>
      </div>

      {/* Main Grid: Urgent Work Orders & Today's Appointments */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Urgent & Unassigned Work Orders */}
        <Card
          title="Unassigned & Urgent Service Requests"
          subtitle="Requires immediate technician dispatch match"
          headerAction={
            <Link to="/work-orders" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
              View All ({workOrders.length})
            </Link>
          }
        >
          {urgentOrders.length === 0 && unassignedOrders.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-500">
              No pending urgent work orders requiring triage.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {(urgentOrders.length > 0 ? urgentOrders : unassignedOrders).slice(0, 5).map((wo) => (
                <div key={wo.id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-800">{wo.work_order_number}</span>
                      <Badge variant="priority" value={wo.priority} size="sm">
                        {wo.priority}
                      </Badge>
                      <Badge variant="category" size="sm">
                        {wo.category}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-600 truncate mt-1">{wo.description}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {wo.service_address.city}, {wo.service_address.state} • ~{wo.estimated_duration_minutes} min
                    </p>
                  </div>
                  <Link to={`/work-orders/${wo.id}`}>
                    <Button variant="outline" size="sm">
                      Inspect
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Appointments Schedule */}
        <Card
          title="Scheduled Appointments"
          subtitle="Upcoming confirmed technician visits"
          headerAction={
            <Link to="/dispatch" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
              Open Schedule Board
            </Link>
          }
        >
          {appointments.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-500">
              No appointments scheduled for today yet.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {appointments.slice(0, 5).map((appt) => (
                <div key={appt.id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-800">{appt.appointment_number}</span>
                      <Badge variant="status" value={appt.status} size="sm">
                        {appt.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-600 mt-1">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>
                        {new Date(appt.scheduled_start).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}{' '}
                        -{' '}
                        {new Date(appt.scheduled_end).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Technician ID: {appt.technician_id.slice(-6)}
                    </p>
                  </div>
                  <Link to={`/work-orders/${appt.work_order_id}`}>
                    <Button variant="ghost" size="sm">
                      Work Order
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

