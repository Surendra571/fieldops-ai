import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Card } from '../components/common/Card';
import { Input } from '../components/common/Input';
import { Button } from '../components/common/Button';
import { Radio, Lock, Mail, Shield, UserCheck, Wrench } from 'lucide-react';

export const LoginView: React.FC = () => {
  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login({ email, password });
      showToast('Successfully authenticated.', 'success', 'Welcome');
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
      showToast(err.message || 'Invalid email or password', 'error', 'Login Failed');
    } finally {
      setIsLoading(false);
    }
  };

  const fillCredentials = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-6">
        <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-700 to-sky-500 items-center justify-center text-white shadow-lg shadow-brand-500/30 mb-3">
          <Radio className="w-7 h-7" />
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          FieldOps <span className="text-brand-600">AI</span>
        </h2>
        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mt-1">
          Production-Minded Field Service Dispatch Platform
        </p>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md px-4">
        <Card className="shadow-lg">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs">
                {error}
              </div>
            )}

            <Input
              label="Email Address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. admin@fieldops.ai"
              required
              leftIcon={<Mail className="w-4 h-4" />}
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              leftIcon={<Lock className="w-4 h-4" />}
            />

            <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isLoading}>
              Sign In to Platform
            </Button>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-100">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Quick One-Click Demo Credentials:
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fillCredentials('admin@fieldops.ai', 'AdminSecurePassword123!')}
                leftIcon={<Shield className="w-3 h-3 text-brand-600" />}
                className="text-[11px]"
              >
                Admin
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fillCredentials('dispatcher@fieldops.ai', 'DispatcherSecure123!')}
                leftIcon={<UserCheck className="w-3 h-3 text-sky-600" />}
                className="text-[11px]"
              >
                Dispatcher
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fillCredentials('marcus.brody@fieldops.ai', 'TechnicianPass123!')}
                leftIcon={<Wrench className="w-3 h-3 text-emerald-600" />}
                className="text-[11px]"
              >
                Technician
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

