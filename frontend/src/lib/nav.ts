import {
  Activity,
  Bot,
  Boxes,
  Database,
  FileBarChart,
  Fuel,
  FlaskConical,
  Network,
  Settings,
  Truck,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  key: string;
  href: string;
  title: string;
  subtitle: string;
  icon: LucideIcon;
  /** 신규 UI 제공 여부. false 면 '준비 중' 화면 (동작하는 척하지 않는다) */
  ready: boolean;
  phase?: "P1" | "P2";
};

export const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "운영",
    items: [
      { key: "control-tower", href: "/control-tower/", title: "Control Tower", subtitle: "통합 운영 현황", icon: Activity, ready: true },
      { key: "network", href: "/network/", title: "Network Intelligence", subtitle: "거점·배송지·외부 위험 지도", icon: Network, ready: false, phase: "P1" },
      { key: "transportation", href: "/transportation/", title: "Transportation", subtitle: "운송비·배차 대안", icon: Truck, ready: false, phase: "P1" },
      { key: "inventory", href: "/inventory/", title: "Demand & Inventory", subtitle: "보충 추천·수요예측", icon: Boxes, ready: false, phase: "P1" },
    ],
  },
  {
    section: "분석",
    items: [
      { key: "fuel-risk", href: "/fuel-risk/", title: "Fuel & Risk", subtitle: "유가 민감도·외부 위험", icon: Fuel, ready: false, phase: "P2" },
      { key: "scenario-lab", href: "/scenario-lab/", title: "Scenario Lab", subtitle: "시나리오 비교·승인", icon: FlaskConical, ready: false, phase: "P1" },
      { key: "copilot", href: "/copilot/", title: "AI Copilot", subtitle: "도구 기반 분석 질의", icon: Bot, ready: false, phase: "P2" },
    ],
  },
  {
    section: "관리",
    items: [
      { key: "data-hub", href: "/data-hub/", title: "Data Hub", subtitle: "업로드·검증·버전", icon: Database, ready: true },
      { key: "reports", href: "/reports/", title: "Reports & Alerts", subtitle: "리포트·알림·조치", icon: FileBarChart, ready: false, phase: "P1" },
      { key: "settings", href: "/settings/", title: "Settings", subtitle: "목표·권한·감사 로그", icon: Settings, ready: false, phase: "P2" },
    ],
  },
];

export const ALL_NAV = NAV.flatMap((s) => s.items);
export const navByKey = (k: string) => ALL_NAV.find((i) => i.key === k)!;
