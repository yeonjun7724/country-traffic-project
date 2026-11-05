// MapLibre 워커(모듈 워커)는 번들러가 경로를 바꾸면 로드에 실패한다 → 정적 파일로 복사해 명시 경로로 사용.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "public", "vendor");
mkdirSync(out, { recursive: true });
copyFileSync(join(root, "node_modules", "maplibre-gl", "dist", "maplibre-gl-worker.mjs"), join(out, "maplibre-gl-worker.mjs"));
console.log("copied maplibre-gl-worker.mjs → public/vendor/");
