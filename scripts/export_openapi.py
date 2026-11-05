"""백엔드 OpenAPI 스키마를 파일로 저장 (프런트 타입 생성용): python scripts/export_openapi.py frontend/openapi.json"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.main import create_app  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/openapi.json")
out.write_text(json.dumps(create_app(seed=False).openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {out}")
