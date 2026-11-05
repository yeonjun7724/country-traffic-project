"""역할 기반 접근 통제 (서비스 계층 · AI 도구 계층 공통 적용)."""
from __future__ import annotations

from dataclasses import dataclass

ROLES = ("viewer", "analyst", "manager", "admin")
ROLE_LABEL = {"viewer": "조회자", "analyst": "분석가", "manager": "운영 관리자", "admin": "관리자"}

# 권한 → 최소 역할
PERMISSIONS: dict[str, str] = {
    "data.read": "viewer",
    "data.export": "analyst",
    "data.upload": "analyst",
    "scenario.save": "analyst",
    "ai.use": "analyst",
    "action.manage": "manager",
    "plan.approve": "manager",
    "dataset.activate": "admin",
    "settings.manage": "admin",
    "audit.read": "manager",
}


class PermissionDenied(Exception):
    pass


@dataclass(frozen=True)
class UserContext:
    user_id: str
    workspace_id: str
    role: str
    display_name: str = ""
    is_demo_workspace: bool = False

    def can(self, permission: str) -> bool:
        need = PERMISSIONS.get(permission)
        if need is None:
            return False  # 정의되지 않은 권한은 거부 (fail-closed)
        return ROLES.index(self.role) >= ROLES.index(need)


def require(ctx: UserContext | None, permission: str) -> None:
    if ctx is None:
        raise PermissionDenied("인증 컨텍스트가 없습니다.")
    if not ctx.can(permission):
        raise PermissionDenied(
            f"권한 부족: '{permission}' 은(는) {ROLE_LABEL[PERMISSIONS.get(permission, 'admin')]} 이상만 가능합니다 "
            f"(현재 역할: {ROLE_LABEL.get(ctx.role, ctx.role)})."
        )
