export type FieldConfidence = 'verified' | 'unverified' | 'uncertain' | 'missing';

export interface ExtractedField<T> {
  value?: T | null;
  confidence: FieldConfidence;
  raw_text?: string | null;
}

export interface ExtractedWorkOrderDraft {
  customer_name?: ExtractedField<string>;
  customer_phone?: ExtractedField<string>;
  customer_email?: ExtractedField<string>;
  service_address?: ExtractedField<string>;
  issue_category?: ExtractedField<string>;
  issue_description?: ExtractedField<string>;
  urgency?: ExtractedField<string>;
  equipment_type?: ExtractedField<string>;
  preferred_window?: ExtractedField<string>;
  required_skills?: ExtractedField<string[]>;
  completeness_score: number;
  missing_required_fields: string[];
  is_ready_for_dispatch: boolean;
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content?: string | null;
  timestamp: string;
}

export interface AgentChatRequest {
  session_id?: string;
  customer_id?: string;
  message: string;
}

export interface AgentChatResponse {
  session_id: string;
  reply: string;
  extracted_draft?: ExtractedWorkOrderDraft | null;
  tools_invoked: string[];
  requires_confirmation: boolean;
  pending_action?: Record<string, any> | null;
  is_escalated: boolean;
  escalation_reason?: string | null;
}

export interface AgentVoiceRequest {
  session_id?: string;
  customer_id?: string;
  audio_base64: string;
  audio_format?: string;
}

export interface AgentVoiceResponse {
  session_id: string;
  user_transcript: string;
  reply_text: string;
  reply_audio_base64: string;
  extracted_draft?: ExtractedWorkOrderDraft | null;
  tools_invoked: string[];
  requires_confirmation: boolean;
  is_escalated: boolean;
  escalation_reason?: string | null;
}

export interface ConversationSession {
  id: string;
  session_id: string;
  customer_id?: string | null;
  work_order_id?: string | null;
  status: string;
  extracted_draft?: ExtractedWorkOrderDraft | null;
  history: ConversationMessage[];
  escalation_reason?: string | null;
  created_at: string;
  updated_at: string;
}

