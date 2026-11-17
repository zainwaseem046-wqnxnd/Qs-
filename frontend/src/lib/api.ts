/**
 * API client. Same-origin requests to /api/v1 (proxied by Next.js), cookie-based auth with
 * double-submit CSRF protection, automatic single-flight token refresh, and typed errors.
 */

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }

  /** Field-level messages from validation errors, keyed by field path. */
  get fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    if (Array.isArray(this.details)) {
      for (const d of this.details as { field?: string; message?: string }[]) {
        if (d.field && d.message) out[d.field] = d.message.replace(/^Value error, /, "");
      }
    }
    return out;
  }
}

const TENANT_KEY = "qs.tenant";
let tenantId: string | null = typeof window !== "undefined" ? safeGet(TENANT_KEY) : null;

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getTenantId(): string | null {
  return tenantId;
}

export function setTenantId(id: string | null): void {
  tenantId = id;
  try {
    if (id) window.localStorage.setItem(TENANT_KEY, id);
    else window.localStorage.removeItem(TENANT_KEY);
  } catch {
    /* storage unavailable: keep in memory only */
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let refreshing: Promise<boolean> | null = null;

export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      setTimeout(() => (refreshing = null), 0);
    });
  return refreshing;
}

type Json = Record<string, unknown> | unknown[];
export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: Json | FormData;
  query?: Record<string, string | number | boolean | null | undefined>;
  tenant?: boolean;
  signal?: AbortSignal;
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    return new ApiError(res.status, body.error.code, body.error.message, body.error.details);
  } catch {
    return new ApiError(res.status, "http_error", `Request failed (${res.status})`);
  }
}

export async function api<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {};
  if (opts.tenant !== false && tenantId) headers["X-Tenant-ID"] = tenantId;
  if (method !== "GET") {
    const csrf = readCookie("qs_csrf");
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) body = opts.body;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(opts.query ?? {})) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const url = `/api/v1${path}${qs.size ? `?${qs}` : ""}`;
  const res = await fetch(url, { method, headers, body, credentials: "same-origin", signal: opts.signal });

  if (res.status === 401 && !retried && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, opts, true);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function downloadUrl(documentId: string, version: number): string {
  return `/api/v1/documents/${documentId}/versions/${version}/download`;
}

/** Download through fetch so the tenant header is sent, then hand the blob to the browser. */
export async function downloadFile(documentId: string, version: number, filename: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (tenantId) headers["X-Tenant-ID"] = tenantId;
  let res = await fetch(downloadUrl(documentId, version), { headers, credentials: "same-origin" });
  if (res.status === 401 && (await refreshSession())) {
    res = await fetch(downloadUrl(documentId, version), { headers, credentials: "same-origin" });
  }
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}
