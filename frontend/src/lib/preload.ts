/**
 * 첫 화면 데이터 선요청 (HTML 파싱 중) — 서버 렌더링 없이 '데이터 대기'를 JS 다운로드·실행과 겹친다.
 *
 * app/layout.tsx 의 <head> 인라인 스크립트(PRELOAD_SCRIPT)가 Control Tower 진입 시 /api/me 와 첫 화면 API 를 바로 요청하고
 * window.__lrPre 에 Promise 를 둔다. 앱의 쿼리 함수는 takePreload() 로 그 결과를 한 번만 이어받고, 이후 요청은 평소처럼 보낸다.
 * - URL(쿼리)이 바뀌었으면 쓰지 않는다 (필터가 다르면 결과도 다름).
 * - 실패하면 reject → 쿼리가 평소 요청으로 다시 시도.
 * - 워크스페이스 헤더는 앱과 같은 규칙 (저장값이 있으면 X-Workspace, 없으면 서버 기본).
 */
type Pre = { sig: string; items: Record<string, Promise<unknown>> };

declare global {
  interface Window {
    __lrPre?: Pre;
  }
}

/** 선요청 결과를 한 번만 꺼낸다. 없거나 URL 이 달라졌으면 null. */
export function takePreload<T>(name: string): Promise<T> | null {
  if (typeof window === "undefined") return null;
  const pre = window.__lrPre;
  if (!pre || pre.sig !== window.location.pathname + window.location.search) return null;
  const p = pre.items[name];
  if (!p) return null;
  delete pre.items[name];
  return p as Promise<T>;
}

const FILTER_KEYS = ["start", "end", "warehouses", "regions", "carriers", "vehicles", "categories", "stores"];

/** <head> 인라인 스크립트 본문. API 주소 접두사는 빌드 시 값 (개발 모드의 별도 API 서버 대응). */
export function preloadScript(apiBase: string): string {
  return `(function(){try{
var L=location;if(L.pathname.indexOf("/control-tower")!==0)return;
var w=null;try{w=localStorage.getItem("lr.workspace")}catch(e){}
var H=w?{"X-Workspace":w}:{};var B=${JSON.stringify(apiBase)};
var sp=new URLSearchParams(L.search),f=new URLSearchParams();
${JSON.stringify(FILTER_KEYS)}.forEach(function(k){sp.getAll(k).forEach(function(v){f.append(k,v)})});
var fq=f.toString();
function g(u){return fetch(B+u,{credentials:"include",headers:H}).then(function(r){if(!r.ok)throw r.status;return r.json()})}
var P={me:g("/api/me"),"ct.overview":g("/api/control-tower/overview"+(fq?"?"+fq:"")),
"ct.network":g("/api/control-tower/network"+(fq?"?"+fq:"")),
"ct.cts.region":g("/api/control-tower/cost-to-serve?dim=region"+(fq?"&"+fq:"")),
"ct.external":g("/api/control-tower/external"),filters:g("/api/filters")};
for(var k in P)P[k].catch(function(){});
window.__lrPre={sig:L.pathname+L.search,items:P};
}catch(e){}})();`;
}
