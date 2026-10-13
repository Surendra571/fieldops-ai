import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { getWorkOrders, createWorkOrder } from '../api/workOrders';
import { getCustomers } from '../api/customers';
import { WorkOrder, WorkOrderCategory, WorkOrderPriority, WorkOrderCreateRequest } from '../types/workOrder';
import { Customer } from '../types/customer';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Select } from '../components/common/Select';
import { Modal } from '../components/common/Modal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useToast } from '../context/ToastContext';
import {
  Search,
  Plus,
  Filter,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  MapPin,
} from 'lucide-react';

export const WorkOrderListView: React.FC = () => {
  const { showToast } = useToast();

  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter States
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedPriority, setSelectedPriority] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  // Pagination
  const [page, setPage] = useState<number>(0);
  const limit = 10;

  // New Work Order Modal
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formData, setFormData] = useState<Partial<WorkOrderCreateRequest>>({
    category: 'HVAC',
    priority: 'MEDIUM',
    estimated_duration_minutes: 60,
    service_address: {
      street: '',
      city: 'Atlanta',
      state: 'GA',
      postal_code: '30309',
    },
  });

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [woRes, custRes] = await Promise.all([
        getWorkOrders({ limit: 100 }),
        getCustomers({ limit: 100 }).catch(() => []),
      ]);
      setWorkOrders(Array.isArray(woRes) ? woRes : ((woRes as any)?.items || []));
      setCustomers(Array.isArray(custRes) ? custRes : ((custRes as any)?.items || []));
    } catch (err: any) {
      setError(err.message || 'Failed to load work orders.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filtered & Paginated items
  const filteredOrders = useMemo(() => {
    return workOrders.filter((wo) => {
      const matchesSearch =
        searchTerm === '' ||
        wo.work_order_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
        wo.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        wo.service_address.city.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus = selectedStatus === 'ALL' || wo.status === selectedStatus;
      const matchesPriority = selectedPriority === 'ALL' || wo.priority === selectedPriority;
      const matchesCategory = selectedCategory === 'ALL' || wo.category === selectedCategory;

      return matchesSearch && matchesStatus && matchesPriority && matchesCategory;
    });
  }, [workOrders, searchTerm, selectedStatus, selectedPriority, selectedCategory]);

  const paginatedOrders = useMemo(() => {
    const start = page * limit;
    return filteredOrders.slice(start, start + limit);
  }, [filteredOrders, page, limit]);

  const totalPages = Math.ceil(filteredOrders.length / limit) || 1;

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.customer_id || !formData.description || !formData.service_address?.street) {
      showToast('Please fill in customer, description, and street address.', 'warning');
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await createWorkOrder(formData as WorkOrderCreateRequest);
      showToast(`Work order ${created.work_order_number} created successfully.`, 'success');
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      showToast(err.message || 'Failed to create work order', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Work Orders</h1>
          <p className="text-sm text-slate-500 mt-1">
            Browse, search, triage, and filter field repair work orders.
          </p>
        </div>
        <Button
          variant="primary"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => {
            if (customers.length > 0 && !formData.customer_id) {
              setFormData((prev) => ({
                ...prev,
                customer_id: customers[0].id,
                service_address: customers[0].service_addresses[0] || prev.service_address,
              }));
            }
            setIsModalOpen(true);
          }}
        >
          Create Work Order
        </Button>
      </div>

      {/* Filter Toolbar */}
      <Card bodyClassName="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="lg:col-span-2">
            <Input
              placeholder="Search by ID, symptom, description, city..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(0);
              }}
              leftIcon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>

          <Select
            options={[
              { value: 'ALL', label: 'All Statuses' },
              { value: 'SUBMITTED', label: 'Submitted' },
              { value: 'TRIAGED', label: 'Triaged' },
              { value: 'SCHEDULED', label: 'Scheduled' },
              { value: 'IN_PROGRESS', label: 'In Progress' },
              { value: 'COMPLETED', label: 'Completed' },
              { value: 'CANCELLED', label: 'Cancelled' },
            ]}
            value={selectedStatus}
            onChange={(e) => {
              setSelectedStatus(e.target.value);
              setPage(0);
            }}
          />

          <Select
            options={[
              { value: 'ALL', label: 'All Priorities' },
              { value: 'EMERGENCY', label: 'Emergency' },
              { value: 'HIGH', label: 'High' },
              { value: 'MEDIUM', label: 'Medium' },
              { value: 'ROUTINE', label: 'Routine' },
            ]}
            value={selectedPriority}
            onChange={(e) => {
              setSelectedPriority(e.target.value);
              setPage(0);
            }}
          />

          <Select
            options={[
              { value: 'ALL', label: 'All Categories' },
              { value: 'HVAC', label: 'HVAC' },
              { value: 'PLUMBING', label: 'Plumbing' },
              { value: 'ELECTRICAL', label: 'Electrical' },
              { value: 'APPLIANCE', label: 'Appliance' },
              { value: 'ROOFING', label: 'Roofing' },
            ]}
            value={selectedCategory}
            onChange={(e) => {
              setSelectedCategory(e.target.value);
              setPage(0);
            }}
          />
        </div>
      </Card>

      {/* Main List */}
      {isLoading ? (
        <LoadingSpinner message="Fetching work orders..." />
      ) : error ? (
        <ErrorBanner title="Failed to load work orders" message={error} onRetry={loadData} />
      ) : filteredOrders.length === 0 ? (
        <EmptyState
          title="No work orders found"
          description="Try clearing your filters or create a new service ticket."
          actionLabel="Clear Filters"
          onAction={() => {
            setSearchTerm('');
            setSelectedStatus('ALL');
            setSelectedPriority('ALL');
            setSelectedCategory('ALL');
          }}
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-100 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Work Order</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Service Address</th>
                  <th className="py-3 px-4">Est. Duration</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {paginatedOrders.map((wo) => (
                  <tr key={wo.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4">
                      <Link to={`/work-orders/${wo.id}`} className="font-mono font-bold text-brand-600 hover:text-brand-700">
                        {wo.work_order_number}
                      </Link>
                      <p className="text-xs text-slate-600 line-clamp-1 max-w-xs mt-0.5">{wo.description}</p>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge variant="priority" value={wo.priority} size="sm">
                        {wo.priority}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge variant="category" size="sm">
                        {wo.category}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge variant="status" value={wo.status} size="sm">
                        {wo.status}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-600">
                      <div className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate max-w-[180px]">
                          {wo.service_address.street}, {wo.service_address.city}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-600">
                      <div className="flex items-center gap-1 font-mono">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span>~{wo.estimated_duration_minutes}m</span>
                        {wo.predicted_by_ml && (
                          <span className="text-[10px] bg-purple-100 text-purple-800 px-1 rounded font-sans font-medium">
                            ML
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link to={`/work-orders/${wo.id}`}>
                        <Button variant="ghost" size="sm">
                          Details
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="px-4 py-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <div>
              Showing <span className="font-semibold text-slate-700">{page * limit + 1}</span> to{' '}
              <span className="font-semibold text-slate-700">
                {Math.min((page + 1) * limit, filteredOrders.length)}
              </span>{' '}
              of <span className="font-semibold text-slate-700">{filteredOrders.length}</span> work orders
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                leftIcon={<ChevronLeft className="w-4 h-4" />}
              >
                Previous
              </Button>
              <span className="font-medium text-slate-700">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                rightIcon={<ChevronRight className="w-4 h-4" />}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Create Work Order Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create New Service Work Order"
        maxWidth="lg"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <Select
            label="Customer"
            options={customers.map((c) => ({
              value: c.id,
              label: `${c.full_name} (${c.phone})`,
            }))}
            value={formData.customer_id || ''}
            onChange={(e) => {
              const cust = customers.find((c) => c.id === e.target.value);
              setFormData((prev) => ({
                ...prev,
                customer_id: e.target.value,
                service_address: cust?.service_addresses[0] || prev.service_address,
              }));
            }}
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Issue Category"
              options={[
                { value: 'HVAC', label: 'HVAC' },
                { value: 'PLUMBING', label: 'Plumbing' },
                { value: 'ELECTRICAL', label: 'Electrical' },
                { value: 'APPLIANCE', label: 'Appliance' },
                { value: 'ROOFING', label: 'Roofing' },
              ]}
              value={formData.category}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, category: e.target.value as WorkOrderCategory }))
              }
              required
            />

            <Select
              label="Priority / Urgency"
              options={[
                { value: 'EMERGENCY', label: 'Emergency' },
                { value: 'HIGH', label: 'High' },
                { value: 'MEDIUM', label: 'Medium' },
                { value: 'ROUTINE', label: 'Routine' },
              ]}
              value={formData.priority}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, priority: e.target.value as WorkOrderPriority }))
              }
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Issue Description <span className="text-rose-500">*</span>
            </label>
            <textarea
              className="w-full text-sm rounded-lg border border-slate-300 p-2.5 focus:ring-2 focus:ring-brand-500 focus:outline-none"
              rows={3}
              placeholder="Detailed description of repair symptoms and customer request..."
              value={formData.description || ''}
              onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
              required
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Input
                label="Street Address"
                value={formData.service_address?.street || ''}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    service_address: { ...prev.service_address!, street: e.target.value },
                  }))
                }
                required
              />
            </div>
            <Input
              label="Postal Code"
              value={formData.service_address?.postal_code || ''}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  service_address: { ...prev.service_address!, postal_code: e.target.value },
                }))
              }
              required
            />
          </div>

          <Input
            label="Estimated Duration (Minutes)"
            type="number"
            min={15}
            max={480}
            value={formData.estimated_duration_minutes || 60}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                estimated_duration_minutes: parseInt(e.target.value) || 60,
              }))
            }
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              Submit Work Order
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

