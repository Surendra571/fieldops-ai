import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, UserRole, LoginRequest } from '../types/auth';
import { login as apiLogin, getMe } from '../api/auth';
import { getAuthToken, setAuthToken, clearAuthToken } from '../api/client';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<User>;
  logout: () => void;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const savedUser = localStorage.getItem('fieldops_user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [token, setTokenState] = useState<string | null>(getAuthToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    clearAuthToken();
    setTokenState(null);
    setUser(null);
  }, []);

  // Listen to global unauthorized event
  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [logout]);

  // Initial token verification
  useEffect(() => {
    const verifyToken = async () => {
      const storedToken = getAuthToken();
      if (!storedToken) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await getMe();
        setUser(currentUser);
        localStorage.setItem('fieldops_user', JSON.stringify(currentUser));
      } catch (err) {
        logout();
      } finally {
        setIsLoading(false);
      }
    };

    verifyToken();
  }, [logout]);

  const login = async (credentials: LoginRequest): Promise<User> => {
    const response = await apiLogin(credentials);
    setAuthToken(response.access_token);
    setTokenState(response.access_token);
    setUser(response.user);
    localStorage.setItem('fieldops_user', JSON.stringify(response.user));
    return response.user;
  };

  const hasRole = (roles: UserRole | UserRole[]): boolean => {
    if (!user) return false;
    const allowed = Array.isArray(roles) ? roles : [roles];
    return allowed.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        logout,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

