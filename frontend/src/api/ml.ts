import { request } from './client';
import {
  DriftMonitoringResponse,
  JobDurationPredictionRequest,
  JobDurationPredictionResponse,
  MissedAppointmentRiskRequest,
  MissedAppointmentRiskResponse,
  ModelMetadataResponse,
} from '../types/ml';

export async function predictDuration(
  data: JobDurationPredictionRequest
): Promise<JobDurationPredictionResponse> {
  return request<JobDurationPredictionResponse>('/ml/predict/duration', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function predictRisk(
  data: MissedAppointmentRiskRequest
): Promise<MissedAppointmentRiskResponse> {
  return request<MissedAppointmentRiskResponse>('/ml/predict/risk', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getModelMetadata(): Promise<ModelMetadataResponse> {
  return request<ModelMetadataResponse>('/ml/models/metadata', {
    method: 'GET',
  });
}

export async function getDriftMonitoring(thresholdPct: number = 35.0): Promise<DriftMonitoringResponse> {
  return request<DriftMonitoringResponse>(`/ml/monitoring/drift?threshold_pct=${thresholdPct}`, {
    method: 'GET',
  });
}

export async function triggerRetraining(
  nSamples: number = 3000,
  seed: number = 42
): Promise<any> {
  return request<any>(`/ml/train?n_samples=${nSamples}&seed=${seed}`, {
    method: 'POST',
  });
}

