import { getToken } from "@/auth/token";

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...options,                                  // spread caller's method/body
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),  // attach JWT if present
      ...options.headers,
    },
  });
  // ... check res.ok, parse, return

  if (!res.ok) {
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = body.detail ?? detail;
  } catch { }
  throw new Error(`${res.status}: ${detail}`);
}
  return (await res.json()) as T;   // the caller decides what T is
}

export async function apiGet<T>(path: string): Promise<T> {
    return apiFetch(path, { method: "GET"})
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
    return apiFetch(path, { method: "POST", body: JSON.stringify(body)})
}