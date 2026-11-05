"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowUp, Bot, ChevronRight, Loader2, RotateCcw, Sparkles, User, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Pill } from "@/components/common/badges";
import { Callout } from "@/components/common/kit";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { navByKey } from "@/lib/nav";
import type { ChatReply, CopilotMeta } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const NAV = navByKey("copilot");
const EXAMPLES = [
  "지난달 배송비가 가장 많이 증가한 거래처는?",
  "경유가격이 15% 오르면 운송사별 운송비는 얼마나 변하나?",
  "배송 지연이 잦은 권역을 보여줘",
  "현재 차량으로 내일 배송 주문을 처리할 수 있나?",
  "영남센터가 중단되면 대체 배송 가능 거점은?",
  "재고 부족 가능성이 높은 SKU를 보여줘",
  "고속도로 취약 영업소 상위 10개",
  "기준 이벤트 전후 화물 교통량 변화",
];

type Msg = { role: "user" | "assistant"; content: string; reply?: ChatReply };
const MODE: Record<string, { label: string; tone: "success" | "warning" | "neutral" | "danger" }> = {
  llm: { label: "LLM + 도구", tone: "success" },
  fallback: { label: "규칙 기반", tone: "warning" },
  unsupported: { label: "지원 범위 밖", tone: "neutral" },
  error: { label: "오류", tone: "danger" },
};

export function CopilotScreen() {
  const { can, me } = useWorkspace();
  const meta = useApi<CopilotMeta>(can("ai.use") ? "/api/copilot/meta" : null, { staleTime: 60_000 });
  const key = `lr.chat.${me?.workspace.id}`;
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [budget, setBudget] = useState<{ used: number; max: number } | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const s = sessionStorage.getItem(key);
      setMsgs(s ? JSON.parse(s) : []);
    } catch {
      setMsgs([]);
    }
  }, [key]);
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(msgs.slice(-30)));
    } catch {
      /* noop */
    }
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, key]);

  const ask = useMutation({
    mutationFn: (q: string) =>
      apiFetch<ChatReply>("/api/copilot/chat", {
        method: "POST",
        body: { message: q, history: msgs.slice(-10).map((m) => ({ role: m.role, content: m.content.slice(0, 8000) })) },
      }),
    onSuccess: (r) => {
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, reply: r }]);
      setBudget({ used: r.calls_used, max: r.calls_max });
    },
    onError: (e) => setMsgs((m) => [...m, { role: "assistant", content: `요청을 처리하지 못했습니다: ${(e as Error).message}`, reply: { answer: "", mode: "error", notice: "", steps: [], results: [], calls_used: 0, calls_max: 0 } }]),
  });

  const send = (q: string) => {
    const t = q.trim();
    if (!t || ask.isPending) return;
    setMsgs((m) => [...m, { role: "user", content: t }]);
    setText("");
    ask.mutate(t);
  };

  if (!can("ai.use"))
    return (
      <>
        <PageHeader nav={NAV} title="분석 Copilot" />
        <Callout tone="warn">AI Copilot 은 분석가 이상 권한이 필요합니다.</Callout>
      </>
    );

  const m = meta.data;
  const used = budget?.used ?? m?.calls_used ?? 0;
  const max = budget?.max ?? m?.calls_max ?? 0;

  return (
    <>
      <PageHeader
        nav={NAV}
        title="분석 Copilot"
        description="계산 도구 결과만 인용합니다 · 읽기 전용 · 권한 범위 안의 데이터만 조회"
        actions={m && <Pill tone={m.llm ? "success" : "warning"}>{m.llm ? `LLM ${m.model}` : "규칙 기반 모드 (API 키 없음)"}</Pill>}
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="flex min-h-[640px] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-card">
          <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite">
            {msgs.length === 0 && (
              <div className="mx-auto max-w-xl py-8 text-center">
                <div className="mx-auto flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow">
                  <Sparkles className="size-5" />
                </div>
                <h2 className="mt-4 text-[17px] font-semibold">무엇을 분석할까요?</h2>
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
                  KPI·운송비·배차·재고·외부 위험을 도구로 계산해 답합니다. 데이터 변경·배차 확정·외부 발송은 하지 않습니다.
                  {!m?.llm && " 지금은 API 키가 없어 정해진 질문 유형만 규칙 기반으로 답합니다."}
                </p>
                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                  {EXAMPLES.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => send(q)}
                      className="rounded-lg border border-border bg-card px-3 py-2.5 text-left text-[12.5px] text-foreground/85 transition-colors hover:border-primary/40 hover:bg-primary/[0.04]"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {msgs.map((msg, i) => (
              <Bubble key={i} msg={msg} />
            ))}
            {ask.isPending && (
              <div className="flex items-center gap-3">
                <Avatar role="assistant" />
                <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm bg-muted px-4 py-3 text-[13px] text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin" /> 도구 실행 · 분석 중…
                </div>
              </div>
            )}
            <div ref={end} />
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
            className="border-t border-border bg-card p-3"
          >
            <div className="flex items-end gap-2 rounded-xl border border-input bg-background px-3 py-2 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/25">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value.slice(0, 2000))}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    send(text);
                  }
                }}
                rows={1}
                placeholder="질문을 입력하세요 (예: 경유가 10% 상승 시 운송사별 연료비)"
                className="max-h-40 min-h-6 flex-1 resize-none bg-transparent text-[13.5px] outline-none placeholder:text-subtle-foreground"
                aria-label="질문 입력"
              />
              <Button type="submit" size="icon-sm" className="rounded-lg" disabled={!text.trim() || ask.isPending} aria-label="보내기">
                <ArrowUp className="size-4" />
              </Button>
            </div>
            <div className="mt-1.5 flex items-center justify-between px-1 text-[11px] text-subtle-foreground">
              <span>Enter 전송 · Shift+Enter 줄바꿈</span>
              {msgs.length > 0 && (
                <button type="button" className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => setMsgs([])}>
                  <RotateCcw className="size-3" /> 대화 초기화
                </button>
              )}
            </div>
          </form>
        </section>
        <aside className="space-y-4">
          <section className="rounded-xl border border-border bg-card p-4 shadow-card">
            <h3 className="text-[13px] font-semibold">이번 세션 LLM 호출</h3>
            <div className="mt-2 flex items-baseline gap-1">
              <span className="text-[22px] font-semibold tabular">{used}</span>
              <span className="text-[12.5px] text-muted-foreground">/ {max}</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: `${max ? Math.min(100, (used / max) * 100) : 0}%` }} />
            </div>
            <p className="mt-2 text-[11.5px] text-subtle-foreground">예산을 넘으면 추가 호출 없이 도구 결과를 그대로 요약합니다.</p>
          </section>
          <section className="rounded-xl border border-border bg-card shadow-card">
            <h3 className="flex items-center gap-1.5 border-b border-border px-4 py-3 text-[13px] font-semibold">
              <Wrench className="size-3.5 text-muted-foreground" /> 사용 가능한 도구 {m?.tools.length ?? ""}
            </h3>
            {!m ? (
              <Skeleton className="m-4 h-40" />
            ) : (
              <ul className="max-h-[420px] divide-y divide-border overflow-y-auto">
                {m.tools.map((t) => (
                  <li key={t.name} className="px-4 py-2">
                    <p className="font-mono text-[11.5px] text-primary">{t.name}</p>
                    <p className="text-[12px] leading-snug text-muted-foreground">{t.description}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  return (
    <span
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-full",
        role === "user" ? "bg-muted text-muted-foreground" : "bg-gradient-to-br from-blue-600 to-indigo-700 text-white",
      )}
      aria-hidden
    >
      {role === "user" ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
    </span>
  );
}

function Bubble({ msg }: { msg: Msg }) {
  if (msg.role === "user")
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-[13.5px] text-primary-foreground">{msg.content}</div>
        <Avatar role="user" />
      </div>
    );
  const r = msg.reply;
  const mode = MODE[r?.mode ?? "fallback"] ?? MODE.fallback;
  return (
    <div className="flex gap-3">
      <Avatar role="assistant" />
      <div className="min-w-0 max-w-[88%] space-y-2">
        <div className="rounded-2xl rounded-tl-sm bg-muted px-4 py-3 text-[13.5px] leading-relaxed">
          <Markdownish text={msg.content} />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Pill tone={mode.tone}>{mode.label}</Pill>
          {r?.notice && <Pill>{r.notice}</Pill>}
        </div>
        {r && r.results.length > 0 && (
          <Collapsible>
            <CollapsibleTrigger className="group inline-flex items-center gap-1 text-[12px] font-medium text-muted-foreground hover:text-foreground">
              <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />
              근거: 도구 호출 결과 ({r.steps.map((s) => s.tool).join(", ")})
            </CollapsibleTrigger>
            <CollapsibleContent>
              <pre className="mt-2 max-h-80 overflow-auto rounded-lg border border-border bg-card p-3 font-mono text-[11px] leading-relaxed text-foreground/80">
                {JSON.stringify(r.results, null, 2)}
              </pre>
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    </div>
  );
}

/** 굵게(**)·목록(-, •)·줄바꿈만 처리하는 안전한 렌더러 (HTML 삽입 없음) */
function Markdownish({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1">
      {lines.map((ln, i) => {
        const bullet = /^\s*[-•*]\s+/.test(ln);
        const body = ln.replace(/^\s*[-•*]\s+/, "");
        const parts = body.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((p, j) =>
          p.startsWith("**") && p.endsWith("**") ? (
            <b key={j} className="font-semibold">
              {p.slice(2, -2)}
            </b>
          ) : p.startsWith("`") && p.endsWith("`") && p.length > 1 ? (
            <span key={j} className="text-[12px] text-muted-foreground">
              {p.slice(1, -1)}
            </span>
          ) : (
            <span key={j}>{p}</span>
          ),
        );
        if (!ln.trim()) return <div key={i} className="h-1.5" />;
        if (/^#{1,4}\s/.test(ln)) return <p key={i} className="pt-1 font-semibold">{ln.replace(/^#{1,4}\s/, "")}</p>;
        return bullet ? (
          <div key={i} className="flex gap-2 pl-1">
            <span className="text-subtle-foreground">•</span>
            <span>{parts}</span>
          </div>
        ) : (
          <p key={i}>{parts}</p>
        );
      })}
    </div>
  );
}
