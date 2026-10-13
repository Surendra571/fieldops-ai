export class ApiError extends Error {
  status: number;
  code?: string;
  details?: any;

  constructor(message: string, status: number, code?: string, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}
const rawApiOrigin = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').trim();
const normalizedOrigin = rawApiOrigin.replace(/\/+$/, '');
const BASE_URL = normalizedOrigin
  ? (normalizedOrigin.endsWith('/api/v1') ? normalizedOrigin : `${normalizedOrigin}/api/v1`)
  : '/api/v1';
export function getAuthToken(): string | null {
  return localStorage.getItem('fieldops_token');
}

export function setAuthToken(token: string): void {
  localStorage.setItem('fieldops_token', token);
}

export function clearAuthToken(): void {
  localStorage.removeItem('fieldops_token');
  localStorage.removeItem('fieldops_user');
}

export interface RequestOptions extends RequestInit {
  idempotencyKey?: string;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  // Add Content-Type if payload exists and not already set
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  // Inject Authorization token if present
  const token = getAuthToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Inject Idempotency-Key if provided
  if (options.idempotencyKey) {
    headers.set('Idempotency-Key', options.idempotencyKey);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Notify session expiration
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  }

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorCode: string | undefined;
    let errorDetails: any;

    try {
      const data = await response.json();
      if (data.error) {
        errorMessage = data.error.message || errorMessage;
        errorCode = data.error.code;
        errorDetails = data.error.details;
      } else if (data.detail) {
        if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        } else if (Array.isArray(data.detail)) {
          errorMessage = data.detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', ');
          errorDetails = data.detail;
        }
      }
    } catch {
      // Fallback to response.statusText
    }

    throw new ApiError(errorMessage, response.status, errorCode, errorDetails);
  }

  // Handle HTTP 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

