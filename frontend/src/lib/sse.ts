import { API_BASE, ApiError, getWorkspace } from "./api";

/**
 * POST 후 Server-Sent Events 를 읽어 이벤트마다 콜백 (fetch 스트림 — EventSource 는 POST·헤더를 못 씀).
 * 인증 쿠키·워크스페이스 헤더 포함. 응답이 스트림이 아니거나 실패하면 ApiError.
 */
export async function postStream<E>(path: string, body: unknown, onEvent: (e: E) => void, signal?: AbortSignal): Promise<void> {
  const ws = getWorkspace();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...(ws ? { "X-Workspace": ws } : {}) },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let msg = `요청 실패 (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j?.detail === "string") msg = j.detail;
    } catch {
      /* noop */
    }
    throw new ApiError(res.status, msg);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, i);
      buf = buf.slice(i + 2);
      for (const line of frame.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as E);
      }
    }
  }
}
