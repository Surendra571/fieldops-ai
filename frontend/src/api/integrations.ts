import { request } from './client';

export interface OutboxMetrics {
  total_events: number;
  pending_count: number;
  pending: number;
  delivered_count: number;
  sent: number;
  dead_letter_count: number;
  dead_letter: number;
  failed_attempts: number;
  failed: number;
  in_flight?: number;
  notifications_sent_total?: number;
  notifications_failed_total?: number;
  notifications_retried_total?: number;
}

export async function getOutboxMetrics(): Promise<OutboxMetrics> {
  const data = await request<any>('/integrations/outbox/metrics', {
    method: 'GET',
  });
  return {
    total_events: data?.total_events ?? 0,
    pending_count: data?.pending_count ?? data?.pending ?? 0,
    pending: data?.pending ?? data?.pending_count ?? 0,
    delivered_count: data?.delivered_count ?? data?.sent ?? 0,
    sent: data?.sent ?? data?.delivered_count ?? 0,
    dead_letter_count: data?.dead_letter_count ?? data?.dead_letter ?? 0,
    dead_letter: data?.dead_letter ?? data?.dead_letter_count ?? 0,
    failed_attempts: data?.failed_attempts ?? data?.failed ?? 0,
    failed: data?.failed ?? data?.failed_attempts ?? 0,
    in_flight: data?.in_flight ?? 0,
    notifications_sent_total: data?.notifications_sent_total ?? 0,
    notifications_failed_total: data?.notifications_failed_total ?? 0,
    notifications_retried_total: data?.notifications_retried_total ?? 0,
  };
}

export async function processOutbox(batchSize: number = 50): Promise<{ processed_count: number; batch_size: number; succeeded: number; failed: number }> {
  const data = await request<any>(`/integrations/outbox/process?limit=${batchSize}`, {
    method: 'POST',
  });
  return {
    processed_count: data?.succeeded ?? data?.batch_size ?? 0,
    batch_size: data?.batch_size ?? 0,
    succeeded: data?.succeeded ?? 0,
    failed: data?.failed ?? 0,
  };
}

