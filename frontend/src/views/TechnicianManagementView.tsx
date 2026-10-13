import React, { useEffect, useState } from 'react';
import { getTechnicians, createTechnician, updateTechnician } from '../api/technicians';
import { Technician, TechnicianCreateRequest, TechnicianStatus, DayOfWeek } from '../types/technician';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Select } from '../components/common/Select';
import { Modal } from '../components/common/Modal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useToast } from '../context/ToastContext';
import {
  Users,
  Plus,
  MapPin,
  Clock,
  Star,
  CheckCircle,
  Shield,
  Activity,
  Edit2,
} from 'lucide-react';

export const TechnicianManagementView: React.FC = () => {
  const { showToast } = useToast();

  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // New Technician Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [newSkillsInput, setNewSkillsInput] = useState('');
  const [formData, setFormData] = useState<TechnicianCreateRequest>({
    name: '',
    phone: '',
    email: '',
    status: 'ACTIVE',
    skills: [],
    max_travel_radius_km: 40.0,
    home_base: {
      type: 'Point',
      coordinates: [-84.3880, 33.7490], // Atlanta
    },
    shift_schedule: {
      timezone: 'America/New_York',
      weekly_hours: [
        { day_of_week: 'MONDAY', start_time: '08:00', end_time: '17:00' },
        { day_of_week: 'TUESDAY', start_time: '08:00', end_time: '17:00' },
        { day_of_week: 'WEDNESDAY', start_time: '08:00', end_time: '17:00' },
        { day_of_week: 'THURSDAY', start_time: '08:00', end_time: '17:00' },
        { day_of_week: 'FRIDAY', start_time: '08:00', end_time: '17:00' },
      ],
    },
  });

  const loadTechnicians = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getTechnicians();
      setTechnicians(Array.isArray(data) ? data : ((data as any)?.items || []));
    } catch (err: any) {
      setError(err.message || 'Failed to fetch field technicians.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTechnicians();
  }, []);

  const handleToggleStatus = async (tech: Technician) => {
    const nextStatus: TechnicianStatus =
      tech.status === 'ACTIVE' ? 'OFF_DUTY' : 'ACTIVE';

    try {
      const updated = await updateTechnician(tech.id, { status: nextStatus });
      setTechnicians((prev) =>
        prev.map((t) => (t.id === tech.id ? { ...t, status: updated.status } : t))
      );
      showToast(`${tech.name} status updated to ${nextStatus}.`, 'info');
    } catch (err: any) {
      showToast(err.message || 'Failed to update technician status.', 'error');
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.phone) {
      showToast('Name, email, and phone are required.', 'warning');
      return;
    }

    const skills = newSkillsInput
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    setIsSubmitting(true);
    try {
      const created = await createTechnician({ ...formData, skills });
      showToast(`Technician ${created.name} registered.`, 'success');
      setIsModalOpen(false);
      setNewSkillsInput('');
      loadTechnicians();
    } catch (err: any) {
      showToast(err.message || 'Failed to create technician.', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Technician Fleet</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage certifications, service radii, shifts, and real-time active availability.
          </p>
        </div>
        <Button
          variant="primary"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => setIsModalOpen(true)}
        >
          Add Field Technician
        </Button>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading technician roster and location data..." />
      ) : error ? (
        <ErrorBanner title="Roster Offline" message={error} onRetry={loadTechnicians} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {technicians.map((tech) => (
            <Card key={tech.id} className="flex flex-col justify-between">
              <div>
                {/* Header Profile */}
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">{tech.name}</h3>
                    <p className="text-xs text-slate-500 mt-0.5">{tech.email}</p>
                    <p className="text-xs font-mono text-slate-400">{tech.phone}</p>
                  </div>
                  <Badge
                    variant={tech.status === 'ACTIVE' ? 'success' : 'neutral'}
                    size="sm"
                  >
                    {tech.status}
                  </Badge>
                </div>

                {/* Rating & Jobs */}
                <div className="flex items-center gap-4 py-2 border-y border-slate-100 text-xs text-slate-600 mb-3">
                  <div className="flex items-center gap-1">
                    <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
                    <span className="font-semibold text-slate-800">{tech.rating || 4.9}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-800">{tech.completed_jobs_count || 120}</span> jobs completed
                  </div>
                </div>

                {/* Certified Skills */}
                <div className="mb-3">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Certified Skills
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {tech.skills.map((skill, i) => (
                      <span
                        key={i}
                        className="text-[11px] font-mono font-medium bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Service Area */}
                <div className="mb-3 text-xs text-slate-600">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Service Area Radius
                  </span>
                  <div className="flex items-center gap-1.5 font-medium">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    <span>Up to {tech.max_travel_radius_km} km from home base</span>
                  </div>
                </div>

                {/* Working Hours */}
                <div className="text-xs text-slate-600">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Shift Schedule
                  </span>
                  <div className="flex items-center gap-1.5 font-medium">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>
                      {tech.shift_schedule?.weekly_hours?.length || 5} days/wk ({tech.shift_schedule?.timezone || 'America/New_York'})
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleToggleStatus(tech)}
                >
                  {tech.status === 'ACTIVE' ? 'Set Off Duty' : 'Set Active'}
                </Button>
                <span className="text-[11px] text-slate-400 font-mono">
                  ID: {tech.id.slice(-6)}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Add Technician Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Register New Field Technician"
        maxWidth="lg"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <Input
            label="Full Name"
            placeholder="e.g. Rachel Adams"
            value={formData.name}
            onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Email Address"
              type="email"
              placeholder="e.g. rachel@fieldops.ai"
              value={formData.email}
              onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
              required
            />
            <Input
              label="Phone Number"
              placeholder="+14045550105"
              value={formData.phone}
              onChange={(e) => setFormData((prev) => ({ ...prev, phone: e.target.value }))}
              required
            />
          </div>

          <Input
            label="Certified Skills (Comma-separated tags)"
            placeholder="e.g. HVAC_EPA_CERTIFIED, HEAT_PUMP_REPAIR"
            value={newSkillsInput}
            onChange={(e) => setNewSkillsInput(e.target.value)}
            helperText="Separate multiple skill certifications by comma"
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Max Travel Radius (km)"
              type="number"
              min={5}
              max={150}
              value={formData.max_travel_radius_km}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  max_travel_radius_km: parseFloat(e.target.value) || 40,
                }))
              }
            />

            <Select
              label="Initial Status"
              options={[
                { value: 'ACTIVE', label: 'ACTIVE' },
                { value: 'OFF_DUTY', label: 'OFF_DUTY' },
                { value: 'ON_LEAVE', label: 'ON_LEAVE' },
              ]}
              value={formData.status}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, status: e.target.value as TechnicianStatus }))
              }
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              Save Technician
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

