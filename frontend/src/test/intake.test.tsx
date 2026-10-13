import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../context/ToastContext';
import { CustomerIntakeView } from '../views/CustomerIntakeView';
import * as agentApi from '../api/agent';

describe('Customer Intake View', () => {
  beforeEach(() => {
    vi.spyOn(agentApi, 'sendChatMessage').mockResolvedValue({
      session_id: 'intake_test_session',
      reply: 'I understand your HVAC heat pump is blowing ambient air. I have created work order draft WO-2026-1045.',
      tools_invoked: ['create_service_request', 'check_customer_history'],
      requires_confirmation: false,
      is_escalated: false,
      extracted_draft: {
        customer_name: { value: 'Eleanor Vance', confidence: 'verified' },
        customer_phone: { value: '+14045550201', confidence: 'verified' },
        service_address: { value: '1428 Elm Street, Atlanta GA', confidence: 'verified' },
        issue_category: { value: 'HVAC', confidence: 'verified' },
        urgency: { value: 'HIGH', confidence: 'verified' },
        completeness_score: 1.0,
        missing_required_fields: [],
        is_ready_for_dispatch: true,
      },
    });
  });

  it('renders chat interface and updates live draft telemetry upon message sending', async () => {
    // Mock scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn();

    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider>
          <ToastProvider>
            <CustomerIntakeView />
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText(/FieldOps Intake Concierge/i)).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/Type your service request/i);
    fireEvent.change(input, {
      target: { value: 'My AC is blowing warm air at 1428 Elm Street.' },
    });

    const sendBtn = screen.getByRole('button', { name: /Send/i });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(agentApi.sendChatMessage).toHaveBeenCalled();
      expect(screen.getByText(/I understand your HVAC heat pump is blowing ambient air/i)).toBeInTheDocument();
      expect(screen.getByText(/create_service_request/i)).toBeInTheDocument();
      expect(screen.getByText(/Ready for Dispatch/i)).toBeInTheDocument();
      expect(screen.getByText(/100%/i)).toBeInTheDocument();
    });
  });
});

