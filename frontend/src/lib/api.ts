/**
 * Fetch-Wrapper für die FastAPI-Backend.
 *
 * - `credentials: "include"` damit Cookies (ff_session, ff_csrf) mitgesendet werden
 * - Bei mutating Calls: liest ff_csrf-Cookie und sendet X-CSRF-Token-Header
 * - CSRF-Cookie ist NICHT HttpOnly (Client muss lesen können)
 */

const CSRF_COOKIE_NAME = "ff_csrf";

function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${CSRF_COOKIE_NAME}=`));
  if (!match) return null;
  return decodeURIComponent(match.split("=")[1] ?? "");
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      // ignore
    }
    const message =
      (detail && typeof detail === "object" && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : null) || `HTTP ${response.status}`;
    throw new ApiError(response.status, message, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function withCsrfHeader(init: RequestInit = {}): RequestInit {
  const csrf = getCsrfToken();
  if (!csrf) return init;
  return {
    ...init,
    headers: {
      ...(init.headers || {}),
      "X-CSRF-Token": csrf,
    },
  };
}

export const api = {
  get: <T>(path: string) =>
    fetch(path, { credentials: "include" }).then(asJson<T>),

  post: <T>(path: string, body?: unknown) =>
    fetch(path, withCsrfHeader({
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })).then(asJson<T>),

  put: <T>(path: string, body?: unknown) =>
    fetch(path, withCsrfHeader({
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })).then(asJson<T>),

  delete: <T = void>(path: string) =>
    fetch(path, withCsrfHeader({
      method: "DELETE",
      credentials: "include",
    })).then(asJson<T>),
};
