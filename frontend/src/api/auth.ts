import { request } from './client';
import { AuthResponse, LoginRequest, User } from '../types/auth';

export async function login(credentials: LoginRequest): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });
}

export async function getMe(): Promise<User> {
  return request<User>('/auth/me', {
    method: 'GET',
  });
}

