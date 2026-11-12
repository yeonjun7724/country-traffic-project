// 번들 크기 회귀 가드 — `npm run build` 뒤에 실행 (npm run check:bundle).
// 라우트별 첫 로딩 JS(gzip)를 계산해 예산을 넘거나, 지도 라이브러리(maplibre)가 첫 로딩에 들어가면 실패한다.
// 기준: docs/IMPROVEMENT_PLAN.md (1차 P1: 708kB → 411kB). 예산을 올려야 한다면 이유를 커밋 메시지에 남긴다.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const next = join(root, ".next");
const BUDGET_KB = Number(process.env.BUNDLE_BUDGET_KB ?? 440); // 라우트당 첫 로딩 JS (gzip)

const manifest = JSON.parse(readFileSync(join(next, "app-build-manifest.json"), "utf8")).pages;
const gz = new Map();
const isMap = new Map();
const sizeOf = (f) => {
  if (!gz.has(f)) {
    const buf = readFileSync(join(next, f));
    gz.set(f, gzipSync(buf, { level: 9 }).length);
    isMap.set(f, (buf.toString("utf8").match(/maplibre/g) ?? []).length > 100);
  }
  return gz.get(f);
};

// 라우트별 레이아웃: 루트 레이아웃 + (app) 그룹 화면은 앱 셸 레이아웃까지
const layoutsOf = (page) => [...(manifest["/layout"] ?? []), ...(page.startsWith("/(app)/") ? (manifest["/(app)/layout"] ?? []) : [])];
const rows = [];
let failed = false;
for (const [page, files] of Object.entries(manifest)) {
  if (!page.endsWith("/page") || page.includes("_not-found")) continue;
  const all = [...new Set([...layoutsOf(page), ...files])].filter((f) => f.endsWith(".js"));
  const kb = all.reduce((s, f) => s + sizeOf(f), 0) / 1024;
  const map = all.some((f) => isMap.get(f));
  const over = kb > BUDGET_KB;
  if (over || map) failed = true;
  rows.push({ route: page.replace("/(app)", "").replace(/\/page$/, "") || "/", "first-load gzip kB": Math.round(kb), maplibre: map ? "포함(실패)" : "", 예산: over ? `초과(${BUDGET_KB})` : "ok" });
}
rows.sort((a, b) => b["first-load gzip kB"] - a["first-load gzip kB"]);
console.table(rows);
if (failed) {
  console.error(`번들 가드 실패: 라우트당 ${BUDGET_KB}kB(gzip) 초과 또는 maplibre 가 첫 로딩에 포함됨 (지도는 next/dynamic 으로만 불러온다 — lib/map-utils 참고)`);
  process.exit(1);
}
console.log(`번들 가드 통과: 모든 라우트 ≤ ${BUDGET_KB}kB, 첫 로딩에 maplibre 없음`);
