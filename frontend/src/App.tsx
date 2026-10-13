import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { AppLayout } from './components/layout/AppLayout';
import { LoginView } from './views/LoginView';
import { DashboardView } from './views/DashboardView';
import { WorkOrderListView } from './views/WorkOrderListView';
import { WorkOrderDetailView } from './views/WorkOrderDetailView';
import { TechnicianManagementView } from './views/TechnicianManagementView';
import { DispatchBoardView } from './views/DispatchBoardView';
import { CustomerIntakeView } from './views/CustomerIntakeView';
import { TechnicianPortalView } from './views/TechnicianPortalView';
import { MLInsightsView } from './views/MLInsightsView';
import { SettingsView } from './views/SettingsView';
import { LoadingSpinner } from './components/common/LoadingSpinner';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <LoadingSpinner message="Verifying session credentials..." />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<LoginView />} />

            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<DashboardView />} />
              <Route path="work-orders" element={<WorkOrderListView />} />
              <Route path="work-orders/:id" element={<WorkOrderDetailView />} />
              <Route path="technicians" element={<TechnicianManagementView />} />
              <Route path="dispatch" element={<DispatchBoardView />} />
              <Route path="intake" element={<CustomerIntakeView />} />
              <Route path="technician-portal" element={<TechnicianPortalView />} />
              <Route path="ml" element={<MLInsightsView />} />
              <Route path="settings" element={<SettingsView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;

