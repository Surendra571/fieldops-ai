import { ServiceAddress } from './workOrder';

export type ChannelPreference = 'VOICE' | 'SMS' | 'EMAIL';

export interface Customer {
  id: string;
  user_id?: string;
  full_name: string;
  phone: string;
  email?: string;
  preferred_channel: ChannelPreference;
  service_addresses: ServiceAddress[];
  total_completed_jobs: number;
  no_show_history_count: number;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreateRequest {
  full_name: string;
  phone: string;
  email?: string;
  preferred_channel?: ChannelPreference;
  service_addresses?: ServiceAddress[];
}

