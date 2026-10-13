import { request } from './client';
import {
  AgentChatRequest,
  AgentChatResponse,
  AgentVoiceRequest,
  AgentVoiceResponse,
  ConversationSession,
} from '../types/agent';

export async function sendChatMessage(data: AgentChatRequest): Promise<AgentChatResponse> {
  return request<AgentChatResponse>('/agent/chat', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function sendVoiceMessage(data: AgentVoiceRequest): Promise<AgentVoiceResponse> {
  return request<AgentVoiceResponse>('/agent/voice', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getSession(sessionId: string): Promise<ConversationSession> {
  return request<ConversationSession>(`/agent/sessions/${sessionId}`, {
    method: 'GET',
  });
}

