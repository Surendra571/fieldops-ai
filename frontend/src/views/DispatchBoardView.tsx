import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { getWorkOrders, getWorkOrderById } from '../api/workOrders';
import { matchCandidates } from '../api/dispatch';
import { createAppointment } from '../api/appointments';
import { WorkOrder } from '../types/workOrder';
import { TechnicianCandidate, MatchCandidatesResponse } from '../types/dispatch';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Select } from '../components/common/Select';
import { Input } from '../components/common/Input';
import { Modal } from '../components/common/Modal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useToast } from '../context/ToastContext';
import {
  Sparkles,
  MapPin,
  Clock,
  Shield,
  Calendar,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ChevronRight,
  TrendingDown,
  Activity,
} from 'lucide-react';

export const DispatchBoardView: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [selectedWoId, setSelectedWoId] = useState<string>(searchParams.get('work_order_id') || '');
  const [targetDate, setTargetDate] = useState<string>(
    new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  );

  const [isLoadingOrders, setIsLoadingOrders] = useState<boolean>(true);
  const [isMatching, setIsMatching] = useState<boolean>(false);
  const [matchResult, setMatchResult] = useState<MatchCandidatesResponse | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<TechnicianCandidate | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  // Booking Confirmation Modal
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState<boolean>(false);
  const [isBooking, setIsBooking] = useState<boolean>(false);
  const [bookingNotes, setBookingNotes] = useState<string>('');

  useEffect(() => {
    const fetchOrders = async () => {
      setIsLoadingOrders(true);
      try {
        const orders = await getWorkOrders({ limit: 50 });
        const safeOrders = Array.isArray(orders) ? orders : ((orders as any)?.items || []);
        setWorkOrders(safeOrders);
        if (!selectedWoId && safeOrders.length > 0) {
          setSelectedWoId(safeOrders[0].id);
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to fetch work orders.', 'error');
      } finally {
        setIsLoadingOrders(false);
      }
    };
    fetchOrders();
  }, [selectedWoId, showToast]);

  const activeWorkOrder = workOrders.find((w) => w.id === selectedWoId);

  const handleMatch = async () => {
    if (!selectedWoId) {
      showToast('Please select a work order to match.', 'warning');
      return;
    }

    setIsMatching(true);
    setMatchResult(null);
    setSelectedCandidate(null);
    setSelectedSlot(null);

    try {
      const res = await matchCandidates({
        work_order_id: selectedWoId,
        target_date: targetDate,
        max_candidates: 5,
      });
      setMatchResult(res);
      if (res.candidates.length > 0) {
        setSelectedCandidate(res.candidates[0]);
        if (res.candidates[0].available_start_times.length > 0) {
          setSelectedSlot(res.candidates[0].available_start_times[0]);
        }
      } else {
        showToast('No eligible technicians found meeting all hard constraints.', 'warning');
      }
    } catch (err: any) {
      showToast(err.message || 'Candidate matching failed.', 'error');
    } finally {
      setIsMatching(false);
    }
  };

  const handleInitiateBooking = (cand: TechnicianCandidate, slotTime: string) => {
    setSelectedCandidate(cand);
    setSelectedSlot(slotTime);
    setIsConfirmModalOpen(true);
  };

  const handleConfirmBooking = async () => {
    if (!activeWorkOrder || !selectedCandidate || !selectedSlot) return;

    setIsBooking(true);
    try {
      const startTime = new Date(selectedSlot);
      const estDuration = activeWorkOrder.estimated_duration_minutes || 60;
      const endTime = new Date(startTime.getTime() + estDuration * 60 * 1000);

      const appt = await createAppointment({
        work_order_id: activeWorkOrder.id,
        technician_id: selectedCandidate.technician_id,
        customer_id: activeWorkOrder.customer_id,
        scheduled_start: startTime.toISOString(),
        scheduled_end: endTime.toISOString(),
        technician_notes: bookingNotes || undefined,
      });

      showToast(`Appointment ${appt.appointment_number} confirmed!`, 'success', 'Booking Confirmed');
      setIsConfirmModalOpen(false);
      navigate(`/work-orders/${activeWorkOrder.id}`);
    } catch (err: any) {
      showToast(err.message || 'Failed to confirm booking.', 'error');
    } finally {
      setIsBooking(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Intelligent Dispatch Board</h1>
        <p className="text-sm text-slate-500 mt-1">
          Constraint-enforced technician matching, predictive duration fitting, and transparent slot scheduling.
        </p>
      </div>

      {/* Target Selector Card */}
      <Card bodyClassName="p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div className="md:col-span-2">
            <Select
              label="Select Work Order for Dispatch"
              options={workOrders.map((wo) => ({
                value: wo.id,
                label: `${wo.work_order_number} — ${wo.category} (${wo.priority}) - ${wo.service_address.city} [${wo.status}]`,
              }))}
              value={selectedWoId}
              onChange={(e) => setSelectedWoId(e.target.value)}
              disabled={isLoadingOrders}
            />
          </div>

          <div>
            <Input
              label="Target Service Date"
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
            />
          </div>
        </div>

        {activeWorkOrder && (
          <div className="mt-4 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-800">Issue:</span>
              <span>{activeWorkOrder.description}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-800">Skills Required:</span>
              <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                {activeWorkOrder.required_skills.join(', ') || 'None specified'}
              </span>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={handleMatch}
              isLoading={isMatching}
              leftIcon={<Sparkles className="w-4 h-4 text-amber-300" />}
            >
              Run Constraint Matching
            </Button>
          </div>
        )}
      </Card>

      {/* Matching Results */}
      {isMatching && <LoadingSpinner message="Evaluating skill constraints, shift schedules, and travel radii..." />}

      {matchResult && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900">
              Matched Candidates ({matchResult.total_eligible} Eligible)
            </h2>
            <span className="text-xs text-slate-500 font-medium">
              Ranked by Multi-Factor Utility (Distance, Workload, SLA Urgency, Duration Fit)
            </span>
          </div>

          {matchResult.candidates.length === 0 ? (
            <Card bodyClassName="p-8 text-center text-slate-500">
              <AlertCircle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
              <p className="font-semibold text-slate-800">No technicians matched all hard constraints</p>
              <p className="text-xs text-slate-500 mt-1">
                Technicians may be off-duty on {targetDate}, outside max travel radius, or lacking certified skills.
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {matchResult.candidates.map((cand, idx) => {
                const breakdown = cand.score_breakdown;
                const isSelected = selectedCandidate?.technician_id === cand.technician_id;

                return (
                  <Card
                    key={cand.technician_id}
                    className={`transition-all ${
                      isSelected ? 'ring-2 ring-brand-500 border-transparent shadow-md' : 'hover:border-slate-300'
                    }`}
                  >
                    <div className="p-5">
                      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                        {/* Left: Tech Info & Score */}
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-brand-700 text-base shrink-0">
                            #{idx + 1}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-bold text-slate-900 text-base">{cand.name}</h3>
                              <span className="text-xs font-mono font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                                Match Score: {(cand.composite_score * 100).toFixed(0)}%
                              </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {breakdown.distance_km.toFixed(1)} km away • ~{breakdown.drive_time_minutes} min drive •{' '}
                              {breakdown.active_jobs_count} active jobs today
                            </p>
                          </div>
                        </div>

                        {/* Middle: Breakdown Badges */}
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          {breakdown.predicted_job_duration_minutes && (
                            <span className="bg-purple-50 text-purple-800 border border-purple-200 px-2 py-1 rounded-md font-mono">
                              ML Duration: ~{breakdown.predicted_job_duration_minutes.toFixed(0)}m
                            </span>
                          )}
                          {breakdown.predicted_missed_risk !== undefined && (
                            <span
                              className={`border px-2 py-1 rounded-md font-mono ${
                                breakdown.predicted_missed_risk < 0.20
                                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                  : breakdown.predicted_missed_risk < 0.45
                                  ? 'bg-amber-50 text-amber-800 border-amber-200'
                                  : 'bg-rose-50 text-rose-800 border-rose-200'
                              }`}
                            >
                              Missed Risk: {(breakdown.predicted_missed_risk * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Natural Language Transparent Explanation */}
                      <div className="mt-3.5 p-3 rounded-lg bg-slate-50 border border-slate-100 text-xs text-slate-700 leading-relaxed">
                        <span className="font-semibold text-slate-800">Recommendation Rationale: </span>
                        {cand.explanation}
                      </div>

                      {/* Slot Options Selection */}
                      <div className="mt-4 pt-3 border-t border-slate-100">
                        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">
                          Available Appointment Slots ({cand.available_start_times.length})
                        </span>
                        {cand.available_start_times.length === 0 ? (
                          <p className="text-xs text-slate-400 italic">No conflict-free slots on this shift</p>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {cand.available_start_times.map((slot) => {
                              const slotDate = new Date(slot);
                              const timeStr = slotDate.toLocaleTimeString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                              });
                              const isThisSlot =
                                isSelected && selectedSlot === slot;

                              return (
                                <button
                                  key={slot}
                                  type="button"
                                  onClick={() => handleInitiateBooking(cand, slot)}
                                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                                    isThisSlot
                                      ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
                                      : 'bg-white text-slate-700 border-slate-200 hover:border-brand-500 hover:bg-brand-50/50'
                                  }`}
                                >
                                  {timeStr}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Explicit Booking Confirmation Gate Modal */}
      <Modal
        isOpen={isConfirmModalOpen}
        onClose={() => setIsConfirmModalOpen(false)}
        title="Confirm Appointment Booking"
        maxWidth="md"
      >
        {activeWorkOrder && selectedCandidate && selectedSlot && (
          <div className="space-y-4">
            <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-xl text-xs text-blue-900 space-y-1">
              <div className="font-bold">Confirmation Gate Check:</div>
              <p>
                You are explicitly committing an appointment for work order{' '}
                <span className="font-mono font-semibold">{activeWorkOrder.work_order_number}</span>.
              </p>
            </div>

            <div className="text-xs space-y-2 text-slate-700">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Technician:</span>
                <span className="font-semibold text-slate-900">{selectedCandidate.name}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Scheduled Start:</span>
                <span className="font-semibold text-slate-900 font-mono">
                  {new Date(selectedSlot).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Duration:</span>
                <span className="font-semibold text-slate-900 font-mono">
                  {activeWorkOrder.estimated_duration_minutes} minutes
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Service Location:</span>
                <span className="font-semibold text-slate-900 text-right truncate max-w-xs">
                  {activeWorkOrder.service_address.street}, {activeWorkOrder.service_address.city}
                </span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Technician Dispatch Notes (Optional)
              </label>
              <textarea
                className="w-full text-xs rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-brand-500 focus:outline-none"
                rows={2}
                placeholder="Gate codes, parking instructions, or customer specific requirements..."
                value={bookingNotes}
                onChange={(e) => setBookingNotes(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="ghost" onClick={() => setIsConfirmModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleConfirmBooking}
                isLoading={isBooking}
                leftIcon={<CheckCircle2 className="w-4 h-4" />}
              >
                Confirm & Book Appointment
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

