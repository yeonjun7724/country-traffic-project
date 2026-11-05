import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./api-types";

export type Schemas = components["schemas"];
export type Metric = Schemas["MetricOut"];
export type Me = Schemas["MeOut"];

/** 개발 시 Next dev 서버(3000)에서 FastAPI(8000)로. 운영은 같은 도메인. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

const WS_KEY = "lr.workspace";

export function getWorkspace(): string | null {
  try {
    return window.localStorage.getItem(WS_KEY);
  } catch {
    return null;
  }
}

export function setWorkspace(id: string) {
  try {
    window.localStorage.setItem(WS_KEY, id);
  } catch {
    /* 저장 불가 환경(시크릿 모드 등) — 세션 동안만 유지 */
  }
  memoryWorkspace = id;
}

let memoryWorkspace: string | null = null;

export function clearWorkspace() {
  memoryWorkspace = null;
  try {
    window.localStorage.removeItem(WS_KEY);
  } catch {
    /* noop */
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const workspaceHeader: Middleware = {
  onRequest({ request }) {
    const ws = memoryWorkspace ?? (typeof window !== "undefined" ? getWorkspace() : null);
    if (ws) request.headers.set("X-Workspace", ws);
    return request;
  },
  async onResponse({ response }) {
    if (response.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.assign(`/login/?next=${next}`);
    }
    return response;
  },
};

export const client = createClient<paths>({ baseUrl: API_BASE, credentials: "include" });
client.use(workspaceHeader);

function detail(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    const d = (error as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => (x as { msg?: string }).msg ?? "").filter(Boolean).join(", ") || fallback;
  }
  return fallback;
}

/** openapi-fetch 결과를 값 또는 ApiError 로 정리. */
export async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (error !== undefined || !response.ok) {
    throw new ApiError(response.status, detail(error, `요청 실패 (${response.status})`));
  }
  return data as T;
}

/** CSV 등 파일 다운로드 (인증 쿠키·워크스페이스 헤더 포함). */
export async function download(path: string, params?: URLSearchParams, fallbackName = "export.csv") {
  const ws = memoryWorkspace ?? getWorkspace();
  const res = await fetch(`${API_BASE}${path}${params && params.toString() ? `?${params}` : ""}`, {
    credentials: "include",
    headers: ws ? { "X-Workspace": ws } : {},
  });
  if (!res.ok) {
    let msg = `내보내기 실패 (${res.status})`;
    try {
      msg = detail(await res.json(), msg);
    } catch {
      /* noop */
    }
    throw new ApiError(res.status, msg);
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** multipart 업로드 (openapi-fetch 대신 fetch — FormData 그대로 전송) */
export async function postForm<T>(path: string, form: FormData): Promise<T> {
  const ws = memoryWorkspace ?? getWorkspace();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    credentials: "include",
    headers: ws ? { "X-Workspace": ws } : {},
  });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* noop */
  }
  if (!res.ok) throw new ApiError(res.status, detail(body, `업로드 실패 (${res.status})`));
  return body as T;
}

/** 스키마가 느슨한(dict) 엔드포인트용 — 응답 타입은 src/lib/types.ts 에서 명시 */
export async function apiFetch<T>(
  path: string,
  opts: { method?: string; query?: Record<string, string | number | string[] | number[] | undefined | null>; body?: unknown } = {},
): Promise<T> {
  const ws = memoryWorkspace ?? getWorkspace();
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(opts.query ?? {})) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => qs.append(k, String(x)));
    else qs.set(k, String(v));
  }
  const res = await fetch(`${API_BASE}${path}${qs.toString() ? `?${qs}` : ""}`, {
    method: opts.method ?? "GET",
    credentials: "include",
    headers: { ...(ws ? { "X-Workspace": ws } : {}), ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* 204 등 */
  }
  if (!res.ok) throw new ApiError(res.status, detail(body, `요청 실패 (${res.status})`));
  return body as T;
}
