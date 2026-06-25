/**
 * API client structure.
 *
 * A single, typed place that knows how to talk to the backend. Centralising
 * this (rather than scattering `fetch` calls across components) means the base
 * URL, error handling, and — later — auth headers live in one file. UI code
 * just calls `api.getHealth()` and never builds URLs by hand.
 *
 * The base URL comes from an environment variable so the same build can point
 * at localhost in development and a real domain in production. `NEXT_PUBLIC_`
 * is required for the value to be available in browser code.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Shape of the backend's liveness response. */
export interface HealthResponse {
  status: string;
  service: string;
}

/**
 * Thin wrapper around `fetch` that prefixes the base URL and throws on non-2xx
 * responses, so callers can rely on a successful return meaning success.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  /** Call the backend liveness probe. */
  getHealth: (): Promise<HealthResponse> => request<HealthResponse>("/health"),
};
