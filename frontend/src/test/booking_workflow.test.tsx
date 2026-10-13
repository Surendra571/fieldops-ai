import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../context/ToastContext';
import { DispatchBoardView } from '../views/DispatchBoardView';
import * as workOrdersApi from '../api/workOrders';
import * as dispatchApi from '../api/dispatch';
import * as appointmentsApi from '../api/appointments';

describe('End-to-End Booking Workflow on Dispatch Board', () => {
  const mockWorkOrders = [
    {
      id: 'wo_test_101',
      work_order_number: 'WO-2026-1001',
      customer_id: 'cust_test_101',
      category: 'HVAC' as const,
      priority: 'HIGH' as const,
      description: 'AC heat pump freezing over and humming loudly',
      symptoms: ['FROZEN_COIL', 'HUMMING'],
      required_skills: ['HVAC_EPA_CERTIFIED'],
      service_address: {
        street: '1428 Elm Street',
        city: 'Atlanta',
        state: 'GA',
        postal_code: '30309',
      },
      source: 'CHAT' as const,
      status: 'SUBMITTED' as const,
      estimated_duration_minutes: 90,
      predicted_by_ml: true,
      audit_trail: [],
      created_at: new Date().toISOString(),
    },
  ];

  const mockMatchResponse = {
    work_order_id: 'wo_test_101',
    target_date: '2026-10-12',
    total_eligible: 1,
    candidates: [
      {
        technician_id: 'tech_brody_01',
        name: 'Marcus Brody',
        skills: ['HVAC_EPA_CERTIFIED', 'HEAT_PUMP_REPAIR'],
        composite_score: 0.92,
        score_breakdown: {
          distance_km: 3.8,
          drive_time_minutes: 6,
          distance_score: 0.91,
          active_jobs_count: 0,
          workload_score: 1.0,
          urgency_score: 0.85,
          duration_fit_score: 1.0,
          predicted_job_duration_minutes: 95.0,
          predicted_missed_risk: 0.12,
        },
        explanation:
          'Marcus Brody is 3.8 km away (~6 min drive). Holds certified skills: [HVAC_EPA_CERTIFIED]. Current daily workload: 0 job(s). ML predicted job duration: 95m. ML missed-appointment risk: LOW (12%). Ranked high for HIGH urgency dispatch. Has 2 available slot(s) on target date.',
        available_start_times: [
          '2026-10-12T09:00:00Z',
          '2026-10-12T13:30:00Z',
        ],
      },
    ],
  };

  const mockCreatedAppointment = {
    id: 'appt_test_901',
    appointment_number: 'APT-2026-0901',
    work_order_id: 'wo_test_101',
    technician_id: 'tech_brody_01',
    customer_id: 'cust_test_101',
    status: 'CONFIRMED' as const,
    scheduled_start: '2026-10-12T09:00:00Z',
    scheduled_end: '2026-10-12T10:30:00Z',
    lock_version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  beforeEach(() => {
    vi.spyOn(workOrdersApi, 'getWorkOrders').mockResolvedValue(mockWorkOrders);
    vi.spyOn(dispatchApi, 'matchCandidates').mockResolvedValue(mockMatchResponse);
    vi.spyOn(appointmentsApi, 'createAppointment').mockResolvedValue(mockCreatedAppointment);
  });

  it('completes the full flow: loads work order, matches candidate, selects slot, and confirms booking', async () => {
    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider>
          <ToastProvider>
            <DispatchBoardView />
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    );

    // 1. Verify Work Order is loaded in selector
    await waitFor(() => {
      expect(screen.getByText(/WO-2026-1001/i)).toBeInTheDocument();
    });

    // 2. Click Run Constraint Matching button
    const matchBtn = screen.getByRole('button', { name: /Run Constraint Matching/i });
    fireEvent.click(matchBtn);

    // 3. Verify Matched candidate card renders with explanation and match score
    await waitFor(() => {
      expect(screen.getByText('Marcus Brody')).toBeInTheDocument();
      expect(screen.getByText(/Match Score: 92%/i)).toBeInTheDocument();
      expect(screen.getByText(/Recommendation Rationale:/i)).toBeInTheDocument();
      expect(screen.getByText(/Marcus Brody is 3.8 km away/i)).toBeInTheDocument();
    });

    // 4. Click an eligible slot time button
    const slotBtns = screen.getAllByRole('button', { name: /\d{1,2}:\d{2}/i });
    expect(slotBtns.length).toBeGreaterThan(0);
    fireEvent.click(slotBtns[0]);

    // 5. Explicit Confirmation Gate Modal appears
    await waitFor(() => {
      expect(screen.getByText(/Confirm Appointment Booking/i)).toBeInTheDocument();
      expect(screen.getByText(/Confirmation Gate Check:/i)).toBeInTheDocument();
    });

    // 6. Click Confirm & Book Appointment
    const confirmBtn = screen.getByRole('button', { name: /Confirm & Book Appointment/i });
    fireEvent.click(confirmBtn);

    // 7. Verify createAppointment API was called with the exact parameters
    await waitFor(() => {
      expect(appointmentsApi.createAppointment).toHaveBeenCalledWith(
        expect.objectContaining({
          work_order_id: 'wo_test_101',
          technician_id: 'tech_brody_01',
          customer_id: 'cust_test_101',
        })
      );
    });
  });
});

