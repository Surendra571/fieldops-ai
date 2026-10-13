export type TechnicianStatus = 'ACTIVE' | 'OFF_DUTY' | 'ON_LEAVE';
export type DayOfWeek =
  | 'MONDAY'
  | 'TUESDAY'
  | 'WEDNESDAY'
  | 'THURSDAY'
  | 'FRIDAY'
  | 'SATURDAY'
  | 'SUNDAY';

export interface ShiftWindow {
  day_of_week: DayOfWeek;
  start_time: string; // HH:MM
  end_time: string;   // HH:MM
}

export interface TechnicianSchedule {
  timezone: string;
  weekly_hours: ShiftWindow[];
}

export interface Technician {
  id: string;
  user_id?: string;
  name: string;
  phone: string;
  email: string;
  status: TechnicianStatus;
  skills: string[];
  home_base?: {
    type: string;
    coordinates: [number, number]; // [lng, lat]
  };
  current_location?: {
    type: string;
    coordinates: [number, number]; // [lng, lat]
  };
  max_travel_radius_km: number;
  shift_schedule?: TechnicianSchedule;
  rating?: number;
  completed_jobs_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface TechnicianCreateRequest {
  name: string;
  phone: string;
  email: string;
  status?: TechnicianStatus;
  skills: string[];
  max_travel_radius_km?: number;
  home_base?: {
    type: string;
    coordinates: [number, number];
  };
  shift_schedule?: TechnicianSchedule;
}

