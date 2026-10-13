import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../context/ToastContext';
import { LoginView } from '../views/LoginView';

describe('LoginView Component', () => {
  it('renders login form with title and input fields', () => {
    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider>
          <ToastProvider>
            <LoginView />
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText(/FieldOps/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In to Platform/i })).toBeInTheDocument();
  });

  it('populates demo credentials when clicking demo buttons', () => {
    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider>
          <ToastProvider>
            <LoginView />
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    );

    const adminBtn = screen.getByRole('button', { name: /Admin/i });
    fireEvent.click(adminBtn);

    const emailInput = screen.getByLabelText(/Email Address/i) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement;

    expect(emailInput.value).toBe('admin@fieldops.ai');
    expect(passwordInput.value).toBe('AdminSecurePassword123!');
  });
});

