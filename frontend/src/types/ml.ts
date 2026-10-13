export interface JobDurationPredictionRequest {
  category: string;
  equipment_type?: string | null;
  equipment_age_years?: number | null;
  urgency: string;
  technician_experience_years?: number | null;
  technician_active_jobs_count?: number;
  historical_jobs_completed?: number;
  distance_km?: number | null;
  estimated_duration_minutes?: number | null;
}

export interface JobDurationPredictionResponse {
  predicted_duration_minutes: number;
  confidence_lower_minutes: number;
  confidence_upper_minutes: number;
  baseline_duration_minutes: number;
  model_version: string;
  used_fallback: boolean;
  latency_ms: number;
}

export interface MissedAppointmentRiskRequest {
  category: string;
  customer_total_jobs?: number;
  customer_no_show_history_count?: number;
  scheduled_hour_of_day?: number;
  scheduled_day_of_week?: number;
  travel_distance_km?: number;
  technician_experience_years?: number | null;
  urgency?: string;
  lead_time_hours?: number;
}

export interface MissedAppointmentRiskResponse {
  risk_probability: number;
  risk_tier: 'LOW' | 'MEDIUM' | 'HIGH';
  baseline_probability: number;
  contributing_factors: string[];
  model_version: string;
  used_fallback: boolean;
  latency_ms: number;
}

export interface ModelDetail {
  name: string;
  version: string;
  model_type: string;
  metrics: Record<string, number>;
  baseline_metrics: Record<string, number>;
  target: string;
}

export interface ModelMetadataResponse {
  status: string;
  version: string;
  trained_at?: string;
  random_seed?: number;
  n_samples?: number;
  split?: {
    train_samples: number;
    val_samples: number;
    test_samples: number;
    method: string;
  };
  models: {
    duration_model: ModelDetail;
    risk_model: ModelDetail;
  };
  baseline_feature_means?: Record<string, number>;
  assumptions_and_limitations?: string[];
}

export interface DriftMonitoringResponse {
  monitoring_window_samples: number;
  feature_means: Record<string, number>;
  baseline_feature_means: Record<string, number>;
  drift_detected: boolean;
  drift_alerts: string[];
}

