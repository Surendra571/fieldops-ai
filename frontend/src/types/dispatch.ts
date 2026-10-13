export interface CandidateScoreBreakdown {
  distance_km: number;
  drive_time_minutes: number;
  distance_score: number;
  active_jobs_count: number;
  workload_score: number;
  urgency_score: number;
  duration_fit_score: number;
  predicted_job_duration_minutes?: number;
  predicted_missed_risk?: number;
}

export interface TechnicianCandidate {
  technician_id: string;
  name: string;
  skills: string[];
  composite_score: number;
  score_breakdown: CandidateScoreBreakdown;
  explanation: string;
  available_start_times: string[];
}

export interface MatchCandidatesRequest {
  work_order_id: string;
  target_date?: string;
  max_candidates?: number;
  weights?: Record<string, number>;
}

export interface MatchCandidatesResponse {
  work_order_id: string;
  target_date: string;
  total_eligible: number;
  candidates: TechnicianCandidate[];
}

