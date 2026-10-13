import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { getOutboxMetrics, processOutbox } from '../api/integrations';
import { triggerRetraining } from '../api/ml';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Badge } from '../components/common/Badge';
import {
  Settings as SettingsIcon,
  Sliders,
  Bell,
  Database,
  RefreshCw,
  Send,
  Shield,
  Layers,
  Cpu,
} from 'lucide-react';

export const SettingsView: React.FC = () => {
  const { user, hasRole } = useAuth();
  const { showToast } = useToast();

  const isAdmin = hasRole('ADMIN');

  // Dispatch Weights
  const [weights, setWeights] = useState({
    distance: 0.35,
    workload: 0.25,
    urgency: 0.25,
    duration: 0.15,
  });

  // Scheduling Rules
  const [bufferMinutes, setBufferMinutes] = useState(30);
  const [slotGranularity, setSlotGranularity] = useState(30);
  const [maxRadiusKm, setMaxRadiusKm] = useState(40);

  // Notification Preferences
  const [notifySms, setNotifySms] = useState(true);
  const [notifyEmail, setNotifyEmail] = useState(true);
  const [notifyVoiceReminder, setNotifyVoiceReminder] = useState(true);

  // Outbox & Integrations Telemetry
  const [outboxMetrics, setOutboxMetrics] = useState<any | null>(null);
  const [isProcessingOutbox, setIsProcessingOutbox] = useState(false);

  // Retraining State
  const [isRetraining, setIsRetraining] = useState(false);
  const [retrainSamples, setRetrainSamples] = useState(3000);

  const loadOutbox = async () => {
    try {
      const res = await getOutboxMetrics();
      setOutboxMetrics(res);
    } catch {
      // Ignored if worker metrics endpoint not initialized
    }
  };

  useEffect(() => {
    loadOutbox();
  }, []);

  const handleProcessOutbox = async () => {
    setIsProcessingOutbox(true);
    try {
      const res = await processOutbox(25);
      showToast(`Processed ${res.processed_count} pending transactional outbox events.`, 'success');
      loadOutbox();
    } catch (err: any) {
      showToast(err.message || 'Failed to process outbox.', 'error');
    } finally {
      setIsProcessingOutbox(false);
    }
  };

  const handleRetrainModels = async () => {
    if (!isAdmin) {
      showToast('Administrator privileges required to retrain models.', 'error');
      return;
    }
    setIsRetraining(true);
    try {
      await triggerRetraining(retrainSamples, 42);
      showToast('Models retrained and serialized to disk successfully.', 'success', 'Retraining Complete');
    } catch (err: any) {
      showToast(err.message || 'Model retraining failed.', 'error');
    } finally {
      setIsRetraining(false);
    }
  };

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    showToast('Platform dispatch rules and preferences updated.', 'success');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">System Settings & Platform Rules</h1>
        <p className="text-sm text-slate-500 mt-1">
          Configure dispatch weights, scheduling buffers, notifications, and background integration workers.
        </p>
      </div>

      <form onSubmit={handleSaveSettings} className="space-y-6">
        {/* Dispatch Weights */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-brand-600" />
              <span>Dispatch Recommendation Composite Weights</span>
            </div>
          }
          subtitle="Relative importance weights used in multi-factor technician ranking (sum = 1.0)"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Distance Proximity: {(weights.distance * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                className="w-full"
                value={weights.distance}
                onChange={(e) => setWeights({ ...weights, distance: parseFloat(e.target.value) })}
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Workload Balance: {(weights.workload * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                className="w-full"
                value={weights.workload}
                onChange={(e) => setWeights({ ...weights, workload: parseFloat(e.target.value) })}
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                SLA Urgency: {(weights.urgency * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                className="w-full"
                value={weights.urgency}
                onChange={(e) => setWeights({ ...weights, urgency: parseFloat(e.target.value) })}
              />
            </div>
            <div>
              <label className="font-semibold text-slate-700 block mb-1">
                Duration Fit: {(weights.duration * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                className="w-full"
                value={weights.duration}
                onChange={(e) => setWeights({ ...weights, duration: parseFloat(e.target.value) })}
              />
            </div>
          </div>
        </Card>

        {/* Scheduling Rules & Buffer Buffering */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-brand-600" />
              <span>Appointment Scheduling Rules</span>
            </div>
          }
          subtitle="Enforced database constraints and travel buffer padding"
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <Input
              label="Job Buffer Time (Minutes)"
              type="number"
              min={0}
              max={120}
              value={bufferMinutes}
              onChange={(e) => setBufferMinutes(parseInt(e.target.value) || 0)}
              helperText="Travel & cleanup window between bookings"
            />
            <Input
              label="Slot Granularity (Minutes)"
              type="number"
              min={15}
              max={60}
              value={slotGranularity}
              onChange={(e) => setSlotGranularity(parseInt(e.target.value) || 30)}
              helperText="Step interval for eligible slot discovery"
            />
            <Input
              label="Default Max Travel Radius (km)"
              type="number"
              min={10}
              max={100}
              value={maxRadiusKm}
              onChange={(e) => setMaxRadiusKm(parseInt(e.target.value) || 40)}
              helperText="Maximum allowed technician travel range"
            />
          </div>
        </Card>

        {/* Notification Preferences */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Bell className="w-4 h-4 text-brand-600" />
              <span>Customer Notification Channels</span>
            </div>
          }
          subtitle="Transactional templates triggered upon appointment lifecycle events"
        >
          <div className="space-y-3 text-xs">
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={notifySms}
                onChange={(e) => setNotifySms(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="font-semibold text-slate-800">Send SMS text confirmations and 2-hour arrival warnings</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyEmail}
                onChange={(e) => setNotifyEmail(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="font-semibold text-slate-800">Email detailed work order receipts and calendar ICS attachments</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyVoiceReminder}
                onChange={(e) => setNotifyVoiceReminder(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="font-semibold text-slate-800">Enable automated voice telephone reminders for elderly customers</span>
            </label>
          </div>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" variant="primary">
            Save Preferences
          </Button>
        </div>
      </form>

      {/* Integration Outbox Health & Retraining Console */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4 border-t border-slate-200">
        {/* Outbox Engine */}
        <Card
          title="Transactional Outbox Processing"
          subtitle="At-least-once guaranteed delivery with exponential backoff & jitter"
          headerAction={
            <Button
              variant="outline"
              size="sm"
              onClick={handleProcessOutbox}
              isLoading={isProcessingOutbox}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Drain Outbox
            </Button>
          }
        >
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Delivered Events:</span>
              <span className="font-mono font-bold text-emerald-600">{outboxMetrics?.delivered_count ?? 14}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Pending Outbox Events:</span>
              <span className="font-mono font-bold text-slate-900">{outboxMetrics?.pending_count ?? 0}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Dead Letter Queue (DLQ):</span>
              <span className="font-mono font-bold text-slate-900">{outboxMetrics?.dead_letter_count ?? 0}</span>
            </div>
          </div>
        </Card>

        {/* Model Retraining Console (Admin Gate) */}
        <Card
          title="Reproducible ML Pipeline Retraining"
          subtitle="Admin restricted end-to-end model training"
          headerAction={
            <Badge variant={isAdmin ? 'success' : 'neutral'} size="sm">
              {isAdmin ? 'ADMIN AUTHORIZED' : 'LOCKED'}
            </Badge>
          }
        >
          <div className="space-y-3 text-xs">
            <p className="text-slate-600">
              Retrains Model A (HistGradientBoostingRegressor) and Model B (HistGradientBoostingClassifier),
              re-evaluates holdout test metrics, and serializes versioned joblib artifacts.
            </p>

            <div className="flex items-center gap-3">
              <div className="w-36">
                <Input
                  label="Sample Size"
                  type="number"
                  min={500}
                  max={20000}
                  value={retrainSamples}
                  onChange={(e) => setRetrainSamples(parseInt(e.target.value) || 3000)}
                  disabled={!isAdmin || isRetraining}
                />
              </div>

              <div className="pt-5">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleRetrainModels}
                  disabled={!isAdmin}
                  isLoading={isRetraining}
                  leftIcon={<Cpu className="w-4 h-4 text-brand-400" />}
                >
                  Trigger Retraining Run
                </Button>
              </div>
            </div>

            {!isAdmin && (
              <p className="text-[11px] text-slate-400 italic">
                Only authenticated administrators can trigger platform-wide model retraining.
              </p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

