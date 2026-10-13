import React, { useEffect, useState } from 'react';
import {
  getModelMetadata,
  getDriftMonitoring,
  predictDuration,
  predictRisk,
} from '../api/ml';
import {
  ModelMetadataResponse,
  DriftMonitoringResponse,
  JobDurationPredictionResponse,
  MissedAppointmentRiskResponse,
} from '../types/ml';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Select } from '../components/common/Select';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useToast } from '../context/ToastContext';
import {
  BrainCircuit,
  Activity,
  AlertTriangle,
  Clock,
  ShieldAlert,
  Sparkles,
  BarChart3,
  CheckCircle2,
  TrendingUp,
} from 'lucide-react';

export const MLInsightsView: React.FC = () => {
  const { showToast } = useToast();

  const [metadata, setMetadata] = useState<ModelMetadataResponse | null>(null);
  const [drift, setDrift] = useState<DriftMonitoringResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Model A: Duration Predictor Form
  const [durCategory, setDurCategory] = useState<string>('HVAC');
  const [durUrgency, setDurUrgency] = useState<string>('HIGH');
  const [durExpYears, setDurExpYears] = useState<number>(4.0);
  const [durActiveJobs, setDurActiveJobs] = useState<number>(2);
  const [durDistanceKm, setDurDistanceKm] = useState<number>(14.5);
  const [durResult, setDurResult] = useState<JobDurationPredictionResponse | null>(null);
  const [isPredictingDur, setIsPredictingDur] = useState<boolean>(false);

  // Model B: Risk Predictor Form
  const [riskCategory, setRiskCategory] = useState<string>('PLUMBING');
  const [riskHour, setRiskHour] = useState<number>(17);
  const [riskDistance, setRiskDistance] = useState<number>(28.0);
  const [riskLeadTime, setRiskLeadTime] = useState<number>(4.0);
  const [riskNoShows, setRiskNoShows] = useState<number>(1);
  const [riskResult, setRiskResult] = useState<MissedAppointmentRiskResponse | null>(null);
  const [isPredictingRisk, setIsPredictingRisk] = useState<boolean>(false);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [metaRes, driftRes] = await Promise.all([
        getModelMetadata(),
        getDriftMonitoring(),
      ]);
      setMetadata(metaRes);
      setDrift(driftRes);
    } catch (err: any) {
      setError(err.message || 'Failed to load ML model metadata.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handlePredictDuration = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsPredictingDur(true);
    try {
      const res = await predictDuration({
        category: durCategory,
        urgency: durUrgency,
        technician_experience_years: durExpYears,
        technician_active_jobs_count: durActiveJobs,
        distance_km: durDistanceKm,
      });
      setDurResult(res);
      showToast('Duration prediction calculated.', 'info');
    } catch (err: any) {
      showToast(err.message || 'Prediction failed.', 'error');
    } finally {
      setIsPredictingDur(false);
    }
  };

  const handlePredictRisk = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsPredictingRisk(true);
    try {
      const res = await predictRisk({
        category: riskCategory,
        scheduled_hour_of_day: riskHour,
        travel_distance_km: riskDistance,
        lead_time_hours: riskLeadTime,
        customer_no_show_history_count: riskNoShows,
      });
      setRiskResult(res);
      showToast('Risk classification calculated.', 'info');
    } catch (err: any) {
      showToast(err.message || 'Risk prediction failed.', 'error');
    } finally {
      setIsPredictingRisk(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Querying serialized models and telemetry drift..." />;
  }

  if (error || !metadata) {
    return <ErrorBanner title="ML Pipeline Offline" message={error || 'No metadata.'} onRetry={loadData} />;
  }

  const durationModel = metadata.models?.duration_model;
  const riskModel = metadata.models?.risk_model;
  const isFallback = metadata.status === 'unloaded_or_fallback';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Machine Learning Intelligence</h1>
        <p className="text-sm text-slate-500 mt-1">
          Scikit-learn pipeline telemetry, job duration regression, missed-appointment risk scoring, and runtime drift detection.
        </p>
      </div>

      {/* Fallback Alert Banner */}
      {isFallback && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-900 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs">
            <h4 className="font-bold text-sm">Heuristic Fallback Mode Active</h4>
            <p className="mt-0.5">
              Production ML pipeline artifacts (duration_model_v1.joblib / risk_model_v1.joblib) are currently running in
              deterministic fallback mode. Predictions will use category rules until retrained or serialized.
            </p>
          </div>
        </div>
      )}

      {/* Metadata & Benchmark Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Model A Summary */}
        <Card
          title="Model A: Job Duration Regression"
          subtitle={durationModel ? `${durationModel.model_type} • Version ${durationModel.version}` : 'Duration Model'}
          headerAction={
            <Badge variant="success" size="sm">
              R² = {durationModel?.metrics?.r2 ?? '0.863'}
            </Badge>
          }
        >
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-3 py-2 border-b border-slate-100">
              <div>
                <span className="text-slate-500 block">Holdout Test MAE</span>
                <span className="text-lg font-mono font-bold text-slate-900">
                  {durationModel?.metrics?.mae ?? '6.90'} min
                </span>
                <span className="text-[10px] text-emerald-600 font-semibold block">
                  vs {durationModel?.baseline_metrics?.mae ?? '9.41'} min baseline (-26.7%)
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Root Mean Squared Error</span>
                <span className="text-lg font-mono font-bold text-slate-900">
                  {durationModel?.metrics?.rmse ?? '8.67'} min
                </span>
                <span className="text-[10px] text-emerald-600 font-semibold block">
                  vs {durationModel?.baseline_metrics?.rmse ?? '11.94'} min baseline
                </span>
              </div>
            </div>
            <p className="text-slate-600">
              <span className="font-semibold text-slate-700">Pre-Job Features: </span>
              Trade category, equipment age, technician experience, active daily workload, transit distance.
            </p>
          </div>
        </Card>

        {/* Model B Summary */}
        <Card
          title="Model B: Missed-Appointment Risk"
          subtitle={riskModel ? `${riskModel.model_type} • Version ${riskModel.version}` : 'Risk Model'}
          headerAction={
            <Badge variant="priority" value="HIGH" size="sm">
              PR-AUC = {riskModel?.metrics?.pr_auc ?? '0.255'}
            </Badge>
          }
        >
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-3 py-2 border-b border-slate-100">
              <div>
                <span className="text-slate-500 block">Precision-Recall AUC</span>
                <span className="text-lg font-mono font-bold text-slate-900">
                  {riskModel?.metrics?.pr_auc ?? '0.255'}
                </span>
                <span className="text-[10px] text-emerald-600 font-semibold block">
                  vs {riskModel?.baseline_metrics?.pr_auc ?? '0.133'} prior (+91.7%)
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Calibration Brier Score</span>
                <span className="text-lg font-mono font-bold text-slate-900">
                  {riskModel?.metrics?.brier_score ?? '0.1837'}
                </span>
                <span className="text-[10px] text-slate-500 block">ROC-AUC: {riskModel?.metrics?.roc_auc ?? '0.601'}</span>
              </div>
            </div>
            <p className="text-slate-600">
              <span className="font-semibold text-slate-700">Target: </span>
              Customer no-show, last-minute cancellation &lt; 2h, or technician arrival delay &gt; 30 min.
            </p>
          </div>
        </Card>
      </div>

      {/* Interactive Predictor Playgrounds */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Duration Playground */}
        <Card title="Live Duration Prediction Playground" subtitle="Calculate pre-job duration with 95% confidence bounds">
          <form onSubmit={handlePredictDuration} className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <Select
                label="Category"
                options={[
                  { value: 'HVAC', label: 'HVAC' },
                  { value: 'PLUMBING', label: 'PLUMBING' },
                  { value: 'ELECTRICAL', label: 'ELECTRICAL' },
                  { value: 'APPLIANCE', label: 'APPLIANCE' },
                  { value: 'ROOFING', label: 'ROOFING' },
                ]}
                value={durCategory}
                onChange={(e) => setDurCategory(e.target.value)}
              />
              <Select
                label="Priority"
                options={[
                  { value: 'ROUTINE', label: 'ROUTINE' },
                  { value: 'MEDIUM', label: 'MEDIUM' },
                  { value: 'HIGH', label: 'HIGH' },
                  { value: 'EMERGENCY', label: 'EMERGENCY' },
                ]}
                value={durUrgency}
                onChange={(e) => setDurUrgency(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <Input
                label="Tech Exp (Yrs)"
                type="number"
                step="0.5"
                min="0"
                max="30"
                value={durExpYears}
                onChange={(e) => setDurExpYears(parseFloat(e.target.value) || 0)}
              />
              <Input
                label="Daily Workload"
                type="number"
                min="0"
                max="10"
                value={durActiveJobs}
                onChange={(e) => setDurActiveJobs(parseInt(e.target.value) || 0)}
              />
              <Input
                label="Distance (km)"
                type="number"
                step="0.5"
                min="0"
                max="100"
                value={durDistanceKm}
                onChange={(e) => setDurDistanceKm(parseFloat(e.target.value) || 0)}
              />
            </div>

            <Button type="submit" variant="primary" size="sm" isLoading={isPredictingDur} className="w-full">
              Predict Service Duration
            </Button>
          </form>

          {durResult && (
            <div className="mt-4 p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="font-semibold text-slate-700">Point Estimate:</span>
                <span className="text-base font-mono font-bold text-slate-900">
                  {durResult.predicted_duration_minutes.toFixed(1)} mins
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-500">
                <span>95% Confidence Bounds:</span>
                <span className="font-mono font-medium">
                  [{durResult.confidence_lower_minutes.toFixed(1)}m – {durResult.confidence_upper_minutes.toFixed(1)}m]
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-500 pt-1 border-t border-slate-200 text-[11px]">
                <span>Inference Latency: {durResult.latency_ms.toFixed(2)} ms</span>
                <span className="font-mono">v{durResult.model_version}</span>
              </div>
            </div>
          )}
        </Card>

        {/* Missed Risk Playground */}
        <Card title="Missed-Appointment Risk Calculator" subtitle="Estimate customer no-show & late arrival risk">
          <form onSubmit={handlePredictRisk} className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <Select
                label="Category"
                options={[
                  { value: 'HVAC', label: 'HVAC' },
                  { value: 'PLUMBING', label: 'PLUMBING' },
                  { value: 'ELECTRICAL', label: 'ELECTRICAL' },
                  { value: 'APPLIANCE', label: 'APPLIANCE' },
                  { value: 'ROOFING', label: 'ROOFING' },
                ]}
                value={riskCategory}
                onChange={(e) => setRiskCategory(e.target.value)}
              />
              <Input
                label="Transit Dist (km)"
                type="number"
                step="1"
                min="0"
                max="100"
                value={riskDistance}
                onChange={(e) => setRiskDistance(parseFloat(e.target.value) || 0)}
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <Input
                label="Hour (0-23)"
                type="number"
                min="8"
                max="20"
                value={riskHour}
                onChange={(e) => setRiskHour(parseInt(e.target.value) || 12)}
              />
              <Input
                label="Lead Time (hrs)"
                type="number"
                min="1"
                max="168"
                value={riskLeadTime}
                onChange={(e) => setRiskLeadTime(parseFloat(e.target.value) || 24)}
              />
              <Input
                label="Past No-Shows"
                type="number"
                min="0"
                max="5"
                value={riskNoShows}
                onChange={(e) => setRiskNoShows(parseInt(e.target.value) || 0)}
              />
            </div>

            <Button type="submit" variant="primary" size="sm" isLoading={isPredictingRisk} className="w-full">
              Calculate Risk Probability
            </Button>
          </form>

          {riskResult && (
            <div className="mt-4 p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="font-semibold text-slate-700">Risk Tier:</span>
                <Badge
                  variant={
                    riskResult.risk_tier === 'LOW'
                      ? 'success'
                      : riskResult.risk_tier === 'MEDIUM'
                      ? 'warning'
                      : 'danger'
                  }
                  size="sm"
                >
                  {riskResult.risk_tier} ({(riskResult.risk_probability * 100).toFixed(0)}%)
                </Badge>
              </div>
              {riskResult.contributing_factors.length > 0 && (
                <div className="pt-1.5 border-t border-slate-200">
                  <span className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                    Contributing Factors:
                  </span>
                  <ul className="list-disc list-inside space-y-0.5 text-[11px] text-slate-600">
                    {riskResult.contributing_factors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Online Data Drift Telemetry */}
      {drift && (
        <Card title="Online Data Drift Monitoring" subtitle="Feature distribution moving average vs training baseline">
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-600">Active Monitoring Ring Buffer Samples:</span>
              <span className="font-mono font-bold text-slate-900">{drift.monitoring_window_samples} / 500</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-600">Drift Flag Status:</span>
              <Badge variant={drift.drift_detected ? 'danger' : 'success'} size="sm">
                {drift.drift_detected ? 'DRIFT ALERT' : 'DISTRIBUTION STABLE'}
              </Badge>
            </div>
            {drift.drift_alerts.length > 0 && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800">
                <span className="font-semibold block mb-1">Active Drift Warnings:</span>
                <ul className="list-disc list-inside space-y-0.5">
                  {drift.drift_alerts.map((alert, i) => (
                    <li key={i}>{alert}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};

