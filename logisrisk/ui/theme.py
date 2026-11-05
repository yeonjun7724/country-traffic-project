"""디자인 토큰 · 라이트/다크 테마 · Plotly 템플릿."""
from __future__ import annotations

TOKENS = {
    "light": {
        "bg": "#f5f7fb", "surface": "#ffffff", "surface-2": "#f8fafc", "border": "#e2e8f0", "border-strong": "#cbd5e1",
        "text-1": "#0f172a", "text-2": "#475569", "text-3": "#94a3b8",
        "brand": "#1e3a8a", "accent": "#2563eb", "accent-soft": "#dbeafe",
        "ok": "#15803d", "ok-soft": "#dcfce7", "warn": "#b45309", "warn-soft": "#fef3c7",
        "bad": "#b91c1c", "bad-soft": "#fee2e2", "info": "#0369a1", "info-soft": "#e0f2fe",
        "nav": "#0b1b3f", "nav-text": "#cbd5e1",
    },
    "dark": {
        "bg": "#0b1220", "surface": "#111a2e", "surface-2": "#0f172a", "border": "#1e293b", "border-strong": "#334155",
        "text-1": "#e2e8f0", "text-2": "#94a3b8", "text-3": "#64748b",
        "brand": "#93c5fd", "accent": "#60a5fa", "accent-soft": "#1e3a8a",
        "ok": "#4ade80", "ok-soft": "#052e16", "warn": "#fbbf24", "warn-soft": "#451a03",
        "bad": "#f87171", "bad-soft": "#450a0a", "info": "#38bdf8", "info-soft": "#082f49",
        "nav": "#060c18", "nav-text": "#94a3b8",
    },
}

# 데이터 성격별 배지 색 (관측/예측/시뮬/가정/외부/DEMO)
KIND_TONE = {"observed": "ok", "derived": "info", "forecast": "warn", "simulated": "warn", "assumption": "warn",
             "external": "info", "demo": "bad"}

SEQ = ["#1d4ed8", "#0891b2", "#f59e0b", "#dc2626", "#7c3aed", "#059669", "#db2777", "#64748b"]
GRADE_COLOR = {"Low": "#94a3b8", "Moderate": "#fbbf24", "High": "#f97316", "Very High": "#dc2626"}
LISA_COLOR = {"High-High": "#dc2626", "High-Low": "#f97316", "Low-High": "#60a5fa", "Low-Low": "#1d4ed8",
              "Not significant": "#cbd5e1"}


def css(mode: str = "light") -> str:
    t = TOKENS[mode]
    var = "".join(f"--{k}:{v};" for k, v in t.items())
    return f"""
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" rel="stylesheet">
<style>
:root {{ {var} --r:10px; --mono:'JetBrains Mono','SFMono-Regular',Consolas,monospace; }}
html, body, [class*="css"], .stApp, button, input, textarea, select {{
  font-family: Pretendard, -apple-system, 'Segoe UI', system-ui, sans-serif !important; }}
.stApp {{ background: var(--bg); color: var(--text-1); }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1480px; }}
h1, h2, h3, h4, p, li, label, .stMarkdown {{ color: var(--text-1); }}
[data-testid="stSidebar"] {{ background: var(--nav); border-right: 1px solid var(--border); }}
[data-testid="stSidebar"] * {{ color: var(--nav-text); }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebar"] a[aria-current="page"] {{ background: rgba(96,165,250,.18); }}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{ color: #e2e8f0; font-size: 13.5px; }}
[data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-baseweb="select"] > div {{ background: #13254a !important; color:#e2e8f0 !important; }}
[data-testid="stSidebar"] [data-baseweb="tag"] {{ background: #1e3a8a !important; }}
[data-testid="stSidebarNavSeparator"] {{ border-color: #1e293b; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ background: var(--surface); border-color: var(--border) !important; border-radius: var(--r); }}
[data-testid="stMetric"] {{ background: var(--surface); }}
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid var(--border); }}
.stTabs [data-baseweb="tab"] {{ padding: 8px 14px; font-size: 13.5px; color: var(--text-2); }}
.stTabs [aria-selected="true"] {{ color: var(--accent) !important; }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 8px; }}
code {{ font-family: var(--mono); }}

.lr-brand {{ display:flex; align-items:center; gap:10px; padding: 4px 4px 14px; }}
.lr-brand-mark {{ width:30px; height:30px; border-radius:8px; background:linear-gradient(135deg,#2563eb,#1e3a8a);
  display:flex; align-items:center; justify-content:center; color:#fff !important; font-weight:800; font-size:14px; }}
.lr-brand-name {{ color:#f8fafc !important; font-weight:700; font-size:15px; line-height:1.1; }}
.lr-brand-sub {{ color:#64748b !important; font-size:10.5px; letter-spacing:.06em; text-transform:uppercase; }}

.lr-top {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap;
  padding-bottom:12px; margin-bottom:14px; border-bottom:1px solid var(--border); }}
.lr-eyebrow {{ font-size:11px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }}
.lr-title {{ font-size:24px; font-weight:750; color:var(--text-1); letter-spacing:-.01em; margin-top:2px; }}
.lr-sub {{ font-size:13px; color:var(--text-2); margin-top:2px; }}
.lr-meta {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }}

.lr-badge {{ display:inline-flex; align-items:center; gap:5px; padding:3px 9px; border-radius:999px; font-size:11.5px;
  font-weight:600; border:1px solid transparent; white-space:nowrap; }}
.lr-badge.ok {{ background:var(--ok-soft); color:var(--ok); }} .lr-badge.warn {{ background:var(--warn-soft); color:var(--warn); }}
.lr-badge.bad {{ background:var(--bad-soft); color:var(--bad); }} .lr-badge.info {{ background:var(--info-soft); color:var(--info); }}
.lr-badge.neutral {{ background:var(--surface-2); color:var(--text-2); border-color:var(--border); }}

.lr-kpi {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--r); padding:14px 16px 12px; height:100%; }}
.lr-kpi-lbl {{ font-size:12px; color:var(--text-2); font-weight:600; display:flex; justify-content:space-between; gap:6px; }}
.lr-kpi-val {{ font-size:24px; font-weight:750; color:var(--text-1); margin:6px 0 4px; font-variant-numeric: tabular-nums; letter-spacing:-.01em; }}
.lr-kpi-val.nc {{ font-size:15px; color:var(--warn); font-weight:650; }}
.lr-kpi-foot {{ font-size:11.5px; color:var(--text-3); display:flex; gap:8px; flex-wrap:wrap; }}
.lr-up {{ color:var(--ok); font-weight:650; }} .lr-down {{ color:var(--bad); font-weight:650; }} .lr-flat {{ color:var(--text-2); }}

.lr-callout {{ border:1px solid var(--border); border-left:4px solid var(--info); background:var(--surface); border-radius:8px;
  padding:10px 14px; font-size:13px; color:var(--text-2); margin:6px 0 12px; }}
.lr-callout b {{ color:var(--text-1); }}
.lr-callout.warn {{ border-left-color:var(--warn); background:var(--warn-soft); }} .lr-callout.bad {{ border-left-color:var(--bad); background:var(--bad-soft); }}
.lr-callout.ok {{ border-left-color:var(--ok); }}
.lr-empty {{ border:1.5px dashed var(--border-strong); border-radius:var(--r); padding:28px; text-align:center; background:var(--surface); }}
.lr-empty-t {{ font-size:15px; font-weight:700; color:var(--text-1); }} .lr-empty-d {{ font-size:13px; color:var(--text-2); margin-top:6px; }}
.lr-sec {{ font-size:15px; font-weight:700; color:var(--text-1); margin:18px 0 8px; display:flex; align-items:center; gap:8px; }}
.lr-sec small {{ font-weight:500; color:var(--text-3); font-size:12px; }}
.lr-def {{ font-size:12px; color:var(--text-2); line-height:1.6; }} .lr-def code {{ font-size:11.5px; }}
.lr-demo {{ background:repeating-linear-gradient(45deg,#fef3c7,#fef3c7 10px,#fde68a 10px,#fde68a 20px); color:#78350f;
  border:1px solid #f59e0b; border-radius:8px; padding:7px 14px; font-weight:700; font-size:12.5px; margin-bottom:10px; }}
</style>"""


def plotly_layout(mode: str = "light", height: int = 320, title: str | None = None) -> dict:
    t = TOKENS[mode]
    lay = dict(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
               font=dict(family="Pretendard, sans-serif", size=12, color=t["text-2"]),
               margin=dict(l=8, r=8, t=36 if title else 10, b=8), colorway=SEQ,
               legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
               xaxis=dict(gridcolor=t["border"], zerolinecolor=t["border"], linecolor=t["border"]),
               yaxis=dict(gridcolor=t["border"], zerolinecolor=t["border"], linecolor=t["border"]),
               hoverlabel=dict(font_family="Pretendard, sans-serif"))
    if title:
        lay["title"] = dict(text=title, x=0, font=dict(size=14, color=t["text-1"]))
    return lay


def map_style(mode: str = "light") -> str:
    return "carto-darkmatter" if mode == "dark" else "carto-positron"
