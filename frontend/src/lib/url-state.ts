/**
 * 같은 화면에서 URL 쿼리를 부분 갱신할 때 쓰는 공용 함수.
 *
 * 여러 곳(탭·전역 필터·Scenario 입력)이 각자 렌더 시점의 쿼리를 기준으로 router.replace 를 부르면,
 * Next 가 앞선 replace 를 아직 반영하기 전에 다음 replace 가 옛 쿼리를 기준으로 덮어써 변경이 사라진다
 * (예: 입력 직후 탭을 누르면 지연된 입력 동기화가 탭을 되돌림). 마지막으로 요청한 쿼리를 기억해 그 위에 쌓는다.
 */
let pending: { path: string; query: string; at: number } | null = null;
const PENDING_MS = 1500;

export function currentQuery(pathname: string, rendered: string): string {
  if (pending && pending.path === pathname && Date.now() - pending.at < PENDING_MS) return pending.query;
  if (typeof window !== "undefined" && window.location.pathname === pathname) return window.location.search.replace(/^\?/, "");
  return rendered;
}

type Router = { replace: (href: string, opts?: { scroll?: boolean }) => void };

/** 현재(또는 진행 중인) 쿼리에 mutate 를 적용해 replace. 바뀐 것이 없으면 이동하지 않는다. */
export function replaceQuery(router: Router, pathname: string, rendered: string, mutate: (q: URLSearchParams) => void) {
  const base = currentQuery(pathname, rendered);
  const q = new URLSearchParams(base);
  mutate(q);
  const next = q.toString();
  if (next === base) return;
  pending = { path: pathname, query: next, at: Date.now() };
  router.replace(`${pathname}${next ? `?${next}` : ""}`, { scroll: false });
}

/** 테스트용 */
export function _resetPendingQuery() {
  pending = null;
}
