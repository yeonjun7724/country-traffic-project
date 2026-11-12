import type { QueryClient } from "@tanstack/react-query";

import type { Me } from "./api";
import { parseFilters } from "./filters";
import { queryDefs } from "./queries";

/**
 * /api/me 응답 직후(React 가 셸·화면을 그리기 전) 현재 화면의 첫 화면 데이터를 미리 요청한다.
 * 느린 기기에서 셸 렌더(~0.9초) 동안 API 가 놀던 구간을 겹친다. 같은 쿼리 정의를 쓰므로 화면 훅은 이 요청을 그대로 이어받는다.
 * 대상은 첫 화면에 보이는 것만 (지연 렌더 영역은 제외).
 */
export function prefetchFirstScreen(qc: QueryClient, me: Me) {
  if (typeof window === "undefined" || !me.has_ops_data) return;
  const ws = me.workspace.id;
  const path = window.location.pathname;
  const f = parseFilters(new URLSearchParams(window.location.search));
  if (path.startsWith("/control-tower")) {
    void qc.prefetchQuery(queryDefs.overview(ws, f));
    void qc.prefetchQuery(queryDefs.network(ws, f));
    void qc.prefetchQuery(queryDefs.cts(ws, f, "region")); // '이번 기간 요약'의 권역 카드
    void qc.prefetchQuery(queryDefs.external(ws));
    void qc.prefetchQuery(queryDefs.filterMeta(ws));
  }
}
