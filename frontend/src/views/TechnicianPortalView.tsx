import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { getAppointments, updateAppointmentStatus } from '../api/appointments';
import { getWorkOrders, updateWorkOrderStatus } from '../api/workOrders';
import { getTechnicians } from '../api/technicians';
import { Appointment, AppointmentStatus } from '../types/appointment';
import { WorkOrder } from '../types/workOrder';
import { Technician } from '../types/technician';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Select } from '../components/common/Select';
import { Modal } from '../components/common/Modal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../context/ToastContext';
import {
  Wrench,
  Navigation,
  CheckCircle2,
  Clock,
  MapPin,
  FileText,
  User,
  AlertCircle,
  Truck,
} from 'lucide-react';

export const TechnicianPortalView: React.FC = () => {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [selectedTechId, setSelectedTechId] = useState<string>('');
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [workOrders, setWorkOrders] = useState<Record<string, WorkOrder>>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Status Update Modal
  const [activeAppt, setActiveAppt] = useState<Appointment | null>(null);
  const [newStatus, setNewStatus] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // 1. Fetch technician roster & select current user or first tech
  useEffect(() => {
    const initTechs = async () => {
      try {
        const techs = await getTechnicians();
        const safeTechs = Array.isArray(techs) ? techs : ((techs as any)?.items || []);
        setTechnicians(safeTechs);
        if (safeTechs.length > 0) {
          // If current user is a technician, find their tech profile
          const matched = safeTechs.find((t: any) => t.email === user?.email);
          setSelectedTechId(matched ? matched.id : safeTechs[0].id);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load technicians.');
      }
    };
    initTechs();
  }, [user]);

  // 2. Fetch appointments for selected technician
  const loadAppointments = async (techId: string) => {
    if (!techId) return;
    setIsLoading(true);
    setError(null);
    try {
      const [appts, orders] = await Promise.all([
        getAppointments({ technician_id: techId }),
        getWorkOrders({ limit: 100 }),
      ]);
      const safeAppts = Array.isArray(appts) ? appts : ((appts as any)?.items || []);
      const safeOrders = Array.isArray(orders) ? orders : ((orders as any)?.items || []);
      setAppointments(safeAppts);

      const woMap: Record<string, WorkOrder> = {};
      safeOrders.forEach((wo: WorkOrder) => {
        woMap[wo.id] = wo;
      });
      setWorkOrders(woMap);
    } catch (err: any) {
      setError(err.message || 'Failed to load technician appointments.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (selectedTechId) {
      loadAppointments(selectedTechId);
    }
  }, [selectedTechId]);

  const handleOpenStatusModal = (appt: Appointment, targetStatus: string) => {
    setActiveAppt(appt);
    setNewStatus(targetStatus);
    setNotes('');
  };

  const handleStatusSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeAppt || !newStatus) return;

    setIsSubmitting(true);
    try {
      const updated = await updateAppointmentStatus(activeAppt.id, newStatus, notes);
      showToast(`Appointment status updated to ${updated.status}.`, 'success');

      // If completing, also update the work order
      if (newStatus === 'COMPLETED' && activeAppt.work_order_id) {
        try {
          await updateWorkOrderStatus(activeAppt.work_order_id, 'COMPLETED', notes || 'Completed by technician in field portal.');
        } catch {
          // Non-blocking if work order transition is already processed
        }
      }

      setActiveAppt(null);
      loadAppointments(selectedTechId);
    } catch (err: any) {
      showToast(err.message || 'Failed to update job status.', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const currentTech = technicians.find((t) => t.id === selectedTechId);

  return (
    <div className="space-y-6">
      {/* Header & Tech Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Technician Mobile Field Portal</h1>
          <p className="text-sm text-slate-500 mt-1">
            Assigned route schedules, on-site diagnostics, and one-tap status transitions.
          </p>
        </div>

        {/* Technician Switcher (helpful for dispatchers/admins simulating technicians) */}
        <div className="w-full sm:w-64">
          <Select
            label="Viewing Technician"
            options={technicians.map((t) => ({
              value: t.id,
              label: `${t.name} (${t.status})`,
            }))}
            value={selectedTechId}
            onChange={(e) => setSelectedTechId(e.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Fetching assigned appointments and job telemetry..." />
      ) : error ? (
        <ErrorBanner title="Failed to load assignments" message={error} onRetry={() => loadAppointments(selectedTechId)} />
      ) : appointments.length === 0 ? (
        <EmptyState
          icon={<Truck className="w-12 h-12 text-slate-400 stroke-1" />}
          title="No jobs assigned today"
          description={`${currentTech?.name || 'Technician'} has no pending scheduled appointments.`}
        />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium px-1">
            <span>{appointments.length} Total Assigned Appointments</span>
            <span>Sorted by scheduled execution window</span>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {appointments.map((appt) => {
              const wo = workOrders[appt.work_order_id];
              const isFinished = appt.status === 'COMPLETED' || appt.status === 'CANCELLED';

              return (
                <Card
                  key={appt.id}
                  className={`border-l-4 ${
                    appt.status === 'IN_PROGRESS' || appt.status === 'ON_SITE'
                      ? 'border-l-amber-500 bg-amber-50/20'
                      : appt.status === 'EN_ROUTE'
                      ? 'border-l-sky-500'
                      : appt.status === 'COMPLETED'
                      ? 'border-l-emerald-500 opacity-90'
                      : 'border-l-brand-600'
                  }`}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    {/* Time & Identification */}
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-800">
                          {appt.appointment_number}
                        </span>
                        <Badge variant="status" value={appt.status} size="sm">
                          {appt.status}
                        </Badge>
                        {wo && (
                          <Badge variant="priority" value={wo.priority} size="sm">
                            {wo.priority}
                          </Badge>
                        )}
                      </div>

                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
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

                      {wo && (
                        <p className="text-xs text-slate-600 font-medium max-w-xl">
                          {wo.description}
                        </p>
                      )}

                      {wo && (
                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                          <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span>
                            {wo.service_address.street}, {wo.service_address.city},{' '}
                            {wo.service_address.state} {wo.service_address.postal_code}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Operational Action Buttons */}
                    <div className="flex items-center gap-2 shrink-0">
                      {!isFinished && (
                        <>
                          {appt.status === 'CONFIRMED' && (
                            <Button
                              variant="outline"
                              size="sm"
                              leftIcon={<Navigation className="w-3.5 h-3.5 text-sky-500" />}
                              onClick={() => handleOpenStatusModal(appt, 'EN_ROUTE')}
                            >
                              En Route
                            </Button>
                          )}

                          {(appt.status === 'EN_ROUTE' || appt.status === 'CONFIRMED') && (
                            <Button
                              variant="outline"
                              size="sm"
                              leftIcon={<Wrench className="w-3.5 h-3.5 text-amber-500" />}
                              onClick={() => handleOpenStatusModal(appt, 'ON_SITE')}
                            >
                              Start Job
                            </Button>
                          )}

                          <Button
                            variant="primary"
                            size="sm"
                            leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                            onClick={() => handleOpenStatusModal(appt, 'COMPLETED')}
                          >
                            Complete
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* State Transition & Notes Modal */}
      <Modal
        isOpen={Boolean(activeAppt)}
        onClose={() => setActiveAppt(null)}
        title={`Transition Job to ${newStatus}`}
      >
        <form onSubmit={handleStatusSubmit} className="space-y-4">
          <p className="text-xs text-slate-600">
            Updating status for appointment <span className="font-mono font-bold">{activeAppt?.appointment_number}</span> to{' '}
            <Badge variant="status" value={newStatus} size="sm">
              {newStatus}
            </Badge>
          </p>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Field Notes / Resolution Summary
            </label>
            <textarea
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:ring-2 focus:ring-brand-500 focus:outline-none"
              rows={3}
              placeholder={
                newStatus === 'COMPLETED'
                  ? 'Replaced capacitor and cleaned blower fan. Tested at 52F supply air.'
                  : 'En route via I-85 North, estimated arrival in 12 mins.'
              }
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setActiveAppt(null)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              Commit Status
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

