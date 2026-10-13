import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getWorkOrderById, updateWorkOrderStatus } from '../api/workOrders';
import { getCustomerById } from '../api/customers';
import { WorkOrder } from '../types/workOrder';
import { Customer } from '../types/customer';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { Select } from '../components/common/Select';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { MaskedText } from '../components/common/MaskedText';
import { useToast } from '../context/ToastContext';
import {
  Calendar,
  Clock,
  MapPin,
  User,
  History,
  AlertTriangle,
  ArrowRight,
  ChevronLeft,
  CheckCircle2,
  HelpCircle,
  Wrench,
} from 'lucide-react';

export const WorkOrderDetailView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { showToast } = useToast();

  const [workOrder, setWorkOrder] = useState<WorkOrder | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Status update modal
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [newStatus, setNewStatus] = useState<string>('');
  const [statusReason, setStatusReason] = useState<string>('');
  const [isSubmittingStatus, setIsSubmittingStatus] = useState(false);

  const loadData = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const wo = await getWorkOrderById(id);
      setWorkOrder(wo);
      setNewStatus(wo.status);

      if (wo.customer_id) {
        try {
          const cust = await getCustomerById(wo.customer_id);
          setCustomer(cust);
        } catch {
          // Non-blocking if customer details fail
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch work order details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const handleStatusSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workOrder || !newStatus) return;

    setIsSubmittingStatus(true);
    try {
      const updated = await updateWorkOrderStatus(workOrder.id, newStatus, statusReason);
      setWorkOrder(updated);
      showToast(`Work order status updated to ${updated.status}.`, 'success');
      setIsStatusModalOpen(false);
      setStatusReason('');
    } catch (err: any) {
      showToast(err.message || 'Status transition failed', 'error');
    } finally {
      setIsSubmittingStatus(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Retrieving work order telemetry and audit record..." />;
  }

  if (error || !workOrder) {
    return (
      <ErrorBanner
        title="Work Order Not Found"
        message={error || 'The requested work order could not be located.'}
        onRetry={loadData}
      />
    );
  }

  // Missing fields warnings detector
  const missingWarnings: string[] = [];
  if (!workOrder.assigned_technician_id) {
    missingWarnings.push('No certified technician has been assigned yet.');
  }
  if (!workOrder.service_address.location?.coordinates) {
    missingWarnings.push('GPS geographic coordinates are missing; proximity scoring will fall back to geocoding.');
  }
  if (workOrder.required_skills.length === 0) {
    missingWarnings.push('No skill requirements specified; any technician in category can match.');
  }
  if (!customer?.phone) {
    missingWarnings.push('Customer primary contact phone is unverified.');
  }

  return (
    <div className="space-y-6">
      {/* Back button & Breadcrumbs */}
      <div className="flex items-center justify-between">
        <Link to="/work-orders" className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800">
          <ChevronLeft className="w-4 h-4" /> Back to Work Orders
        </Link>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsStatusModalOpen(true)}
          >
            Update Status ({workOrder.status})
          </Button>
          <Link to={`/dispatch?work_order_id=${workOrder.id}`}>
            <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-4 h-4" />}>
              Dispatch Technician
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Header Banner */}
      <Card bodyClassName="p-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xl font-bold text-slate-900">{workOrder.work_order_number}</span>
              <Badge variant="priority" value={workOrder.priority}>
                {workOrder.priority}
              </Badge>
              <Badge variant="category">{workOrder.category}</Badge>
              <Badge variant="status" value={workOrder.status}>
                {workOrder.status}
              </Badge>
            </div>
            <h2 className="text-lg font-semibold text-slate-800 mt-2">{workOrder.description}</h2>
            <p className="text-xs text-slate-400 mt-1">
              Created on {new Date(workOrder.created_at).toLocaleString()} via{' '}
              <span className="font-semibold uppercase">{workOrder.source}</span>
            </p>
          </div>
          <div className="text-right sm:border-l sm:border-slate-100 sm:pl-6">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Est. Duration</span>
            <div className="text-2xl font-bold font-mono text-slate-900 mt-0.5">
              {workOrder.estimated_duration_minutes} <span className="text-sm font-normal text-slate-500">min</span>
            </div>
            {workOrder.predicted_by_ml && (
              <span className="inline-block mt-1 text-[11px] font-semibold text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded-full">
                ML Predicted
              </span>
            )}
          </div>
        </div>
      </Card>

      {/* Missing Fields Warnings */}
      {missingWarnings.length > 0 && (
        <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/80 text-amber-900">
          <div className="flex items-center gap-2 font-semibold text-sm mb-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            Field Operational Alerts & Missing Attributes ({missingWarnings.length})
          </div>
          <ul className="text-xs space-y-1 list-disc list-inside text-amber-800 ml-1">
            {missingWarnings.map((warn, i) => (
              <li key={i}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Grid: Customer & Location vs Symptoms & Technical Specs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Customer Information & Service Location */}
        <Card title="Customer & Service Location">
          <div className="space-y-4 text-sm">
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Customer Profile</span>
              <div className="font-medium text-slate-900 text-base mt-0.5">
                {customer?.full_name || 'Anonymous Customer'}
              </div>
              <div className="grid grid-cols-2 gap-3 mt-2">
                <div>
                  <span className="text-xs text-slate-400 block">Phone</span>
                  <MaskedText value={customer?.phone || ''} type="phone" />
                </div>
                <div>
                  <span className="text-xs text-slate-400 block">Email</span>
                  <MaskedText value={customer?.email || ''} type="email" />
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Service Address</span>
              <div className="flex items-start gap-2 mt-1.5">
                <MapPin className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                <div className="text-slate-800">
                  <p className="font-medium">{workOrder.service_address.street}</p>
                  <p className="text-xs text-slate-500">
                    {workOrder.service_address.city}, {workOrder.service_address.state}{' '}
                    {workOrder.service_address.postal_code}
                  </p>
                  {workOrder.service_address.location?.coordinates && (
                    <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                      GPS: [{workOrder.service_address.location.coordinates[0].toFixed(4)},{' '}
                      {workOrder.service_address.location.coordinates[1].toFixed(4)}]
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Symptoms, Required Skills & AI Extraction */}
        <Card title="Diagnosis & Required Skills">
          <div className="space-y-4 text-sm">
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                Required Technical Skills
              </span>
              {workOrder.required_skills.length === 0 ? (
                <span className="text-xs text-slate-400 italic">No specific skill certifications required</span>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {workOrder.required_skills.map((skill, i) => (
                    <span key={i} className="text-xs font-mono font-medium bg-slate-100 border border-slate-200 text-slate-800 px-2 py-0.5 rounded-md">
                      {skill}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-100">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                Reported Symptoms & Diagnostics
              </span>
              {workOrder.symptoms.length === 0 ? (
                <span className="text-xs text-slate-400 italic">No symptom tags attached</span>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {workOrder.symptoms.map((symptom, i) => (
                    <span key={i} className="text-xs font-medium bg-sky-50 border border-sky-200 text-sky-800 px-2 py-0.5 rounded-md">
                      {symptom}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {workOrder.preferred_time_window && (
              <div className="pt-3 border-t border-slate-100">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Customer Time Preference</span>
                <p className="text-xs text-slate-700 mt-1">
                  Preferred Date: <span className="font-semibold">{workOrder.preferred_time_window.preferred_date || 'Earliest available'}</span> (
                  {workOrder.preferred_time_window.time_of_day})
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Audit History Timeline */}
      <Card title="Audit History & State Transitions" subtitle="Verifiable event transitions recorded on the immutable ledger">
        {workOrder.audit_trail.length === 0 ? (
          <div className="text-center py-6 text-xs text-slate-400 italic">
            Initial submitted state; no subsequent state transitions recorded yet.
          </div>
        ) : (
          <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
            {workOrder.audit_trail.map((transition, idx) => (
              <div key={transition.transition_id || idx} className="relative">
                <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-brand-600 ring-4 ring-white" />
                <div className="flex items-center gap-2">
                  <Badge variant="status" value={transition.from_status} size="sm">
                    {transition.from_status}
                  </Badge>
                  <span className="text-slate-400 text-xs">→</span>
                  <Badge variant="status" value={transition.to_status} size="sm">
                    {transition.to_status}
                  </Badge>
                  <span className="text-xs text-slate-400 ml-auto">
                    {new Date(transition.timestamp).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-1 font-medium">Actor: {transition.actor}</p>
                {transition.reason && (
                  <p className="text-xs text-slate-500 italic mt-0.5">Reason: "{transition.reason}"</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Status Transition Modal */}
      <Modal
        isOpen={isStatusModalOpen}
        onClose={() => setIsStatusModalOpen(false)}
        title="Update Work Order Status"
      >
        <form onSubmit={handleStatusSubmit} className="space-y-4">
          <Select
            label="New Lifecycle Status"
            options={[
              { value: 'SUBMITTED', label: 'SUBMITTED' },
              { value: 'TRIAGED', label: 'TRIAGED' },
              { value: 'SCHEDULED', label: 'SCHEDULED' },
              { value: 'IN_PROGRESS', label: 'IN_PROGRESS' },
              { value: 'COMPLETED', label: 'COMPLETED' },
              { value: 'CANCELLED', label: 'CANCELLED' },
              { value: 'FAILED', label: 'FAILED' },
            ]}
            value={newStatus}
            onChange={(e) => setNewStatus(e.target.value)}
            required
          />

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Reason / Transition Notes
            </label>
            <textarea
              className="w-full text-sm rounded-lg border border-slate-300 p-2.5 focus:ring-2 focus:ring-brand-500 focus:outline-none"
              rows={2}
              placeholder="Operational rationale for state change..."
              value={statusReason}
              onChange={(e) => setStatusReason(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsStatusModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmittingStatus}>
              Commit Transition
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

