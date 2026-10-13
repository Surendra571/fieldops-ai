import React, { useState, useEffect, useRef } from 'react';
import { sendChatMessage, sendVoiceMessage } from '../api/agent';
import { AgentChatResponse, ExtractedWorkOrderDraft } from '../types/agent';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { useToast } from '../context/ToastContext';
import {
  Mic,
  MicOff,
  Send,
  Bot,
  User,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Volume2,
  RefreshCw,
  Cpu,
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  tools?: string[];
  audioBase64?: string;
}

export const CustomerIntakeView: React.FC = () => {
  const { showToast } = useToast();

  const [sessionId] = useState<string>(() => `intake_sess_${Date.now()}`);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: 'Hello! I am your FieldOps AI intake concierge. How can I assist you with your repair or maintenance service today?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputText, setInputText] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [draft, setDraft] = useState<ExtractedWorkOrderDraft | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim()) return;

    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: 'user',
      text: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsSending(true);

    try {
      const response: AgentChatResponse = await sendChatMessage({
        session_id: sessionId,
        message: text.trim(),
      });

      if (response.extracted_draft) {
        setDraft(response.extracted_draft);
      }

      const agentMsg: ChatMessage = {
        id: `agent_${Date.now()}`,
        sender: 'agent',
        text: response.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        tools: response.tools_invoked,
      };

      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      showToast(err.message || 'Failed to communicate with intake agent.', 'error');
    } finally {
      setIsSending(false);
    }
  };

  // Simulated Voice Interaction using real base64 mock
  const handleVoiceToggle = async () => {
    if (!isRecording) {
      setIsRecording(true);
      showToast('Listening... Speak your service request.', 'info', 'Microphone Active');

      // Simulate a 3.5s speech capture, then submit to /agent/voice
      setTimeout(async () => {
        setIsRecording(false);
        setIsSending(true);

        try {
          // Dummy valid wave header base64 audio
          const dummyAudioBase64 = 'UklGRiQAAABXQVZFRm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
          const voiceRes = await sendVoiceMessage({
            session_id: sessionId,
            audio_base64: dummyAudioBase64,
            audio_format: 'wav',
          });

          // Add user transcript
          const userMsg: ChatMessage = {
            id: `voice_usr_${Date.now()}`,
            sender: 'user',
            text: voiceRes.user_transcript || 'My HVAC heat pump is blowing ambient air and making a humming sound.',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          };

          // Add agent reply
          const agentMsg: ChatMessage = {
            id: `voice_agent_${Date.now()}`,
            sender: 'agent',
            text: voiceRes.reply_text,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            tools: voiceRes.tools_invoked,
            audioBase64: voiceRes.reply_audio_base64,
          };

          if (voiceRes.extracted_draft) {
            setDraft(voiceRes.extracted_draft);
          }

          setMessages((prev) => [...prev, userMsg, agentMsg]);
          showToast('Speech processed and synthesized audio returned.', 'success');
        } catch (err: any) {
          showToast(err.message || 'Voice service error.', 'error');
        } finally {
          setIsSending(false);
        }
      }, 3000);
    } else {
      setIsRecording(false);
    }
  };

  const playSynthesizedAudio = (base64Audio: string) => {
    try {
      const audio = new Audio(`data:audio/wav;base64,${base64Audio}`);
      audio.play();
    } catch {
      showToast('Audio playback not supported in this browser environment.', 'warning');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Voice & Chat Customer Intake</h1>
        <p className="text-sm text-slate-500 mt-1">
          Autonomous conversational agent extracting structured work orders, resolving customer identity, and booking slots.
        </p>
      </div>

      {/* Main Grid: Conversation Pane vs Extracted Draft Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Chat / Voice Console (2 Cols) */}
        <div className="lg:col-span-2">
          <Card
            title={
              <div className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-brand-600" />
                <span>FieldOps Intake Concierge</span>
              </div>
            }
            subtitle={`Session: ${sessionId}`}
            bodyClassName="p-0"
          >
            {/* Messages Thread */}
            <div className="h-[460px] overflow-y-auto p-4 space-y-4 bg-slate-50/50">
              {messages.map((msg) => {
                const isUser = msg.sender === 'user';
                return (
                  <div
                    key={msg.id}
                    className={`flex items-start gap-2.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white ${
                        isUser ? 'bg-slate-800' : 'bg-brand-600'
                      }`}
                    >
                      {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>
                    <div
                      className={`max-w-[80%] rounded-2xl p-3.5 text-sm shadow-sm ${
                        isUser
                          ? 'bg-brand-600 text-white rounded-tr-none'
                          : 'bg-white text-slate-800 border border-slate-200/80 rounded-tl-none'
                      }`}
                    >
                      <p className="leading-relaxed whitespace-pre-line">{msg.text}</p>

                      {/* Tool Calls pill */}
                      {msg.tools && msg.tools.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-100 flex items-center gap-1.5 flex-wrap">
                          <Cpu className="w-3.5 h-3.5 text-slate-400" />
                          <span className="text-[11px] text-slate-400 font-semibold uppercase">Invoked:</span>
                          {msg.tools.map((t, idx) => (
                            <span
                              key={idx}
                              className="text-[10px] font-mono bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border border-slate-200"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* TTS Audio Player button */}
                      {msg.audioBase64 && (
                        <div className="mt-2 pt-2 border-t border-slate-100 flex items-center">
                          <button
                            type="button"
                            onClick={() => playSynthesizedAudio(msg.audioBase64!)}
                            className="inline-flex items-center gap-1.5 text-xs text-brand-600 font-semibold hover:text-brand-800"
                          >
                            <Volume2 className="w-3.5 h-3.5" /> Play Voice Response
                          </button>
                        </div>
                      )}

                      <span
                        className={`text-[10px] mt-1 block text-right ${
                          isUser ? 'text-brand-200' : 'text-slate-400'
                        }`}
                      >
                        {msg.timestamp}
                      </span>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            {/* Quick Prompt Chips */}
            <div className="p-3 bg-white border-t border-slate-100 flex items-center gap-2 overflow-x-auto text-xs">
              <span className="text-slate-400 font-semibold shrink-0">Sample prompts:</span>
              <button
                type="button"
                onClick={() =>
                  handleSendMessage(
                    'My name is Eleanor Vance, phone +14045550201 at 1428 Elm Street Atlanta. My AC heat pump is blowing ambient air and making a loud humming sound.'
                  )
                }
                className="shrink-0 bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-full border border-slate-200 transition-colors"
              >
                HVAC Emergency Repair
              </button>
              <button
                type="button"
                onClick={() =>
                  handleSendMessage(
                    'Hello, kitchen sink pipe burst and leaking under counter at 742 Evergreen Terrace Atlanta.'
                  )
                }
                className="shrink-0 bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-full border border-slate-200 transition-colors"
              >
                Plumbing Leak
              </button>
            </div>

            {/* Input Bar */}
            <div className="p-3 bg-white border-t border-slate-100 flex items-center gap-2">
              <button
                type="button"
                onClick={handleVoiceToggle}
                className={`p-2.5 rounded-xl border transition-all ${
                  isRecording
                    ? 'bg-rose-500 text-white border-rose-600 animate-pulse'
                    : 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200'
                }`}
                title={isRecording ? 'Recording audio...' : 'Start voice audio intake'}
                aria-label="Voice input"
              >
                {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>

              <input
                type="text"
                placeholder={isRecording ? 'Listening to speech...' : 'Type your service request or answer concierge questions...'}
                className="flex-1 text-sm bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                disabled={isSending || isRecording}
              />

              <Button
                variant="primary"
                onClick={() => handleSendMessage()}
                isLoading={isSending}
                disabled={isRecording || !inputText.trim()}
                aria-label="Send message"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </Card>
        </div>

        {/* Real-time Extracted Draft Inspector (1 Col) */}
        <div>
          <Card
            title={
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-600" />
                <span>Extracted Work Order Draft</span>
              </div>
            }
            subtitle="Deterministic Pydantic validation state"
          >
            {draft ? (
              <div className="space-y-4 text-xs">
                {/* Completeness Bar */}
                <div>
                  <div className="flex justify-between items-center mb-1 font-semibold text-slate-700">
                    <span>Intake Completeness</span>
                    <span>{(draft.completeness_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        draft.completeness_score >= 0.8
                          ? 'bg-emerald-500'
                          : draft.completeness_score >= 0.5
                          ? 'bg-amber-500'
                          : 'bg-rose-500'
                      }`}
                      style={{ width: `${draft.completeness_score * 100}%` }}
                    />
                  </div>
                </div>

                {/* Extracted Fields */}
                <div className="divide-y divide-slate-100">
                  <div className="py-1.5 flex justify-between">
                    <span className="text-slate-500">Customer:</span>
                    <span className="font-semibold text-slate-900">{draft.customer_name?.value || '—'}</span>
                  </div>
                  <div className="py-1.5 flex justify-between">
                    <span className="text-slate-500">Phone:</span>
                    <span className="font-mono text-slate-900">{draft.customer_phone?.value || '—'}</span>
                  </div>
                  <div className="py-1.5 flex justify-between">
                    <span className="text-slate-500">Address:</span>
                    <span className="font-semibold text-slate-900 text-right truncate max-w-[150px]">
                      {draft.service_address?.value || '—'}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between">
                    <span className="text-slate-500">Category:</span>
                    <Badge variant="category" size="sm">
                      {draft.issue_category?.value || 'UNRESOLVED'}
                    </Badge>
                  </div>
                  <div className="py-1.5 flex justify-between">
                    <span className="text-slate-500">Urgency:</span>
                    <Badge variant="priority" value={draft.urgency?.value || 'MEDIUM'} size="sm">
                      {draft.urgency?.value || 'MEDIUM'}
                    </Badge>
                  </div>
                </div>

                {/* Missing Required Fields Alert */}
                {draft.missing_required_fields.length > 0 && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900">
                    <span className="font-semibold block mb-1">Missing for Dispatch:</span>
                    <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                      {draft.missing_required_fields.map((f, i) => (
                        <li key={i}>{f.replace('_', ' ')}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Ready Badge */}
                <div className="pt-2 text-center">
                  {draft.is_ready_for_dispatch ? (
                    <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" /> Ready for Dispatch
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-slate-500 bg-slate-100 border border-slate-200 px-3 py-1 rounded-full">
                      Awaiting Required Fields
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-400 italic">
                Send a message or voice audio to watch the AI concierge extract work order parameters in real time.
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

