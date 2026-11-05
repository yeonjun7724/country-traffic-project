"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Loader2,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { DataTable } from "@/components/common/data-table";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { client, download, postForm, unwrap, type Schemas } from "@/lib/api";
import { num } from "@/lib/format";
import { useSchema } from "@/lib/queries";
import { cn } from "@/lib/utils";

import { Dropzone } from "./dropzone";

type Upload = Schemas["UploadOut"];
type Validation = Schemas["ValidationOut"];
type Field = Schemas["FieldSpecOut"];
const NONE = "__none__";

const STEPS = ["파일 선택", "컬럼 매핑", "검증 결과", "저장 완료"];

export function UploadWizard({ entity, label, isDemo }: { entity: string; label: string; isDemo: boolean }) {
  const qc = useQueryClient();
  const schema = useSchema(entity);
  const [upload, setUpload] = useState<Upload | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Validation | null>(null);
  const [ack, setAck] = useState(false);
  const [done, setDone] = useState<Schemas["CommitOut"] | null>(null);

  const reset = () => {
    if (upload) void client.DELETE("/api/data/uploads/{upload_id}", { params: { path: { upload_id: upload.upload_id } } });
    setUpload(null);
    setMapping({});
    setResult(null);
    setAck(false);
    setDone(null);
  };

  const uploadMut = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("entity", entity);
      fd.append("file", f);
      return postForm<Upload>("/api/data/uploads", fd);
    },
    onSuccess: (u) => {
      setUpload(u);
      setMapping(u.auto_mapping);
      setResult(null);
    },
    onError: (e) => toast.error("파일을 읽을 수 없습니다", { description: (e as Error).message }),
  });

  const sheetMut = useMutation({
    mutationFn: (sheet: string) =>
      unwrap(client.PUT("/api/data/uploads/{upload_id}/sheet", { params: { path: { upload_id: upload!.upload_id } }, body: { mapping: {}, sheet } })),
    onSuccess: (u) => {
      setUpload(u);
      setMapping(u.auto_mapping);
      setResult(null);
    },
    onError: (e) => toast.error("시트를 읽을 수 없습니다", { description: (e as Error).message }),
  });

  const validateMut = useMutation({
    mutationFn: () =>
      unwrap(client.POST("/api/data/uploads/{upload_id}/validate", { params: { path: { upload_id: upload!.upload_id } }, body: { mapping } })),
    onSuccess: (r) => {
      setResult(r);
      setAck(false);
    },
    onError: (e) => toast.error("검증 실패", { description: (e as Error).message }),
  });

  const commitMut = useMutation({
    mutationFn: () =>
      unwrap(
        client.POST("/api/data/uploads/{upload_id}/commit", {
          params: { path: { upload_id: upload!.upload_id } },
          body: { acknowledge_excluded_rows: ack },
        }),
      ),
    onSuccess: (r) => {
      setDone(r);
      qc.invalidateQueries();
      toast.success(`${label} v${r.version} 저장 완료`, { description: `${num(r.rows)}행 · 이전 버전은 보존됩니다.` });
    },
    onError: (e) => toast.error("저장 실패 — 변경 사항 없음", { description: (e as Error).message }),
  });

  const fields = schema.data?.fields ?? [];
  const dupSources = useMemo(() => {
    const seen = new Map<string, number>();
    Object.values(mapping).forEach((c) => c && seen.set(c, (seen.get(c) ?? 0) + 1));
    return new Set([...seen].filter(([, n]) => n > 1).map(([c]) => c));
  }, [mapping]);
  const missingRequired = fields.filter((f) => f.required && !mapping[f.name]);
  const stale = !!result && JSON.stringify(sortObj(result.validated_mapping)) !== JSON.stringify(sortObj(clean(mapping)));
  const step = done ? 3 : result && !stale ? 2 : upload ? 1 : 0;

  return (
    <div className="space-y-5">
      <Stepper step={step} />

      {done ? (
        <Done label={label} done={done} onAnother={reset} />
      ) : !upload ? (
        <div className="space-y-3">
          <Dropzone onFile={(f) => uploadMut.mutate(f)} busy={uploadMut.isPending} label={label} />
          <div className="flex flex-wrap items-center justify-between gap-2 text-[12.5px] text-muted-foreground">
            <span>한글·영문 컬럼명은 자동으로 매핑됩니다. 저장 전까지 데이터는 바뀌지 않습니다.</span>
            <Button
              variant="link"
              size="sm"
              className="h-auto p-0"
              onClick={() => download(`/api/data/templates/${entity}.csv`, undefined, `template_${entity}.csv`).catch((e) => toast.error((e as Error).message))}
            >
              <Download className="size-3.5" /> {label} 표준 양식 받기
            </Button>
          </div>
          {isDemo && <DemoReload />}
        </div>
      ) : (
        <>
          <FileBar upload={upload} onReset={reset} onSheet={(s) => sheetMut.mutate(s)} sheetBusy={sheetMut.isPending} />
          <Preview upload={upload} />
          <MappingTable
            fields={fields}
            columns={upload.columns}
            mapping={mapping}
            auto={upload.auto_mapping}
            dup={dupSources}
            onChange={(f, c) => setMapping((m) => ({ ...m, [f]: c }))}
          />
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
            <p className="text-[12.5px] text-muted-foreground">
              {dupSources.size > 0 ? (
                <span className="font-medium text-danger">하나의 원본 컬럼을 여러 필드에 매핑할 수 없습니다.</span>
              ) : stale ? (
                <span className="font-medium text-warning">검증 후 매핑이 바뀌었습니다. 다시 검증하세요.</span>
              ) : missingRequired.length > 0 ? (
                <span className="text-warning">필수 필드 미매핑: {missingRequired.map((f) => f.label).join(", ")} — 검증에서 오류로 표시됩니다.</span>
              ) : (
                "매핑을 확인한 뒤 검증을 실행하세요. 타입·필수값·범위·중복·참조·좌표·날짜를 검사합니다."
              )}
            </p>
            <Button onClick={() => validateMut.mutate()} disabled={validateMut.isPending || dupSources.size > 0}>
              {validateMut.isPending ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
              {result ? "다시 검증" : "검증 실행"}
            </Button>
          </div>
          {result && !stale && (
            <Results
              r={result}
              upload={upload}
              ack={ack}
              onAck={setAck}
              committing={commitMut.isPending}
              onCommit={() => commitMut.mutate()}
              label={label}
            />
          )}
        </>
      )}
    </div>
  );
}

function clean(m: Record<string, string>) {
  return Object.fromEntries(Object.entries(m).filter(([, v]) => v));
}
function sortObj(m: Record<string, string>) {
  return Object.fromEntries(Object.entries(m).sort(([a], [b]) => a.localeCompare(b)));
}

function Stepper({ step }: { step: number }) {
  return (
    <ol className="flex items-center gap-2" aria-label="업로드 단계">
      {STEPS.map((s, i) => (
        <li key={s} className="flex flex-1 items-center gap-2" aria-current={i === step ? "step" : undefined}>
          <span
            className={cn(
              "flex size-6 shrink-0 items-center justify-center rounded-full text-[11.5px] font-semibold",
              i < step && "bg-success text-white",
              i === step && "bg-primary text-primary-foreground",
              i > step && "bg-muted text-subtle-foreground",
            )}
          >
            {i < step ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
          </span>
          <span className={cn("hidden text-[12.5px] sm:inline", i === step ? "font-semibold text-foreground" : "text-muted-foreground")}>{s}</span>
          {i < STEPS.length - 1 && <span className={cn("h-px flex-1", i < step ? "bg-success/50" : "bg-border")} />}
        </li>
      ))}
    </ol>
  );
}

function FileBar({ upload, onReset, onSheet, sheetBusy }: { upload: Upload; onReset: () => void; onSheet: (s: string) => void; sheetBusy: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5">
      <FileSpreadsheet className="size-5 text-success" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium">{upload.filename}</p>
        <p className="text-[12px] text-muted-foreground tabular">
          {num(upload.n_rows)}행 × {upload.columns.length}열
        </p>
      </div>
      {upload.sheets.length > 1 && (
        <Select value={upload.sheet ?? undefined} onValueChange={onSheet} disabled={sheetBusy}>
          <SelectTrigger size="sm" className="w-40" aria-label="시트 선택">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {upload.sheets.map((s) => (
              <SelectItem key={s} value={s}>
                시트: {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <Button variant="ghost" size="sm" onClick={onReset}>
        <X className="size-3.5" /> 다른 파일
      </Button>
    </div>
  );
}

function Preview({ upload }: { upload: Upload }) {
  const cols = upload.columns.slice(0, 30);
  return (
    <details className="group rounded-lg border border-border bg-card" open={false}>
      <summary className="cursor-pointer list-none px-3 py-2 text-[12.5px] font-medium text-muted-foreground hover:text-foreground">
        <span className="mr-1 inline-block transition-transform group-open:rotate-90">›</span> 원본 미리보기 (상위 {Math.min(20, upload.n_rows)}행)
      </summary>
      <div className="max-h-72 overflow-auto border-t border-border">
        <table className="w-full text-[12px]">
          <thead className="sticky top-0 bg-muted">
            <tr>
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-3 py-1.5 text-left font-medium text-muted-foreground">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {upload.preview.map((r, i) => (
              <tr key={i} className="border-t border-border">
                {cols.map((c) => (
                  <td key={c} className="max-w-48 truncate whitespace-nowrap px-3 py-1.5">
                    {r[c] == null ? <span className="text-subtle-foreground">—</span> : String(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function MappingTable({
  fields,
  columns,
  mapping,
  auto,
  dup,
  onChange,
}: {
  fields: Field[];
  columns: string[];
  mapping: Record<string, string>;
  auto: Record<string, string>;
  dup: Set<string>;
  onChange: (field: string, col: string) => void;
}) {
  const mapped = fields.filter((f) => mapping[f.name]).length;
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <h3 className="text-[13px] font-semibold">컬럼 매핑</h3>
        <span className="text-[12px] text-muted-foreground tabular">
          {mapped}/{fields.length} 필드 매핑 · <span className="text-danger">*</span> 필수
        </span>
      </div>
      <div className="grid divide-y divide-border md:grid-cols-2 md:divide-y-0">
        {[fields.slice(0, Math.ceil(fields.length / 2)), fields.slice(Math.ceil(fields.length / 2))].map((half, hi) => (
          <div key={hi} className={cn("divide-y divide-border", hi === 1 && "md:border-l md:border-border")}>
            {half.map((f) => {
              const v = mapping[f.name] ?? "";
              const isAuto = !!v && auto[f.name] === v;
              const bad = !!v && dup.has(v);
              return (
                <div key={f.name} className="flex items-center gap-3 px-4 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1 text-[13px] font-medium">
                      {f.label}
                      {f.required && <span className="text-danger">*</span>}
                    </div>
                    <div className="truncate font-mono text-[11px] text-subtle-foreground">
                      {f.name}
                      {f.unit ? ` · ${f.unit}` : ""}
                      {f.allowed?.length ? ` · ${f.allowed.join("/")}` : ""}
                    </div>
                  </div>
                  <Select value={v || NONE} onValueChange={(c) => onChange(f.name, c === NONE ? "" : c)}>
                    <SelectTrigger
                      size="sm"
                      className={cn("w-44", bad && "border-danger text-danger", !v && f.required && "border-warning/60")}
                      aria-label={`${f.label} 에 매핑할 원본 컬럼`}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NONE}>
                        <span className="text-muted-foreground">(매핑 안 함)</span>
                      </SelectItem>
                      {columns.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="w-11 shrink-0">
                    {isAuto && (
                      <span className="inline-flex items-center gap-0.5 whitespace-nowrap rounded-sm bg-primary/10 px-1 text-[10.5px] font-medium text-primary" title="컬럼명으로 자동 매핑">
                        <Sparkles className="size-2.5" />
                        자동
                      </span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

const ERR_COLS: ColumnDef<Record<string, unknown>, unknown>[] = [
  { accessorKey: "row", header: "행", meta: { align: "right" } },
  { accessorKey: "column", header: "컬럼", cell: (c) => <span className="font-mono text-[12px]">{String(c.getValue() ?? "")}</span> },
  { accessorKey: "message", header: "사유" },
  {
    accessorKey: "value",
    header: "값",
    cell: (c) => <span className="font-mono text-[12px] text-muted-foreground">{c.getValue() == null ? "—" : String(c.getValue())}</span>,
  },
];

function Results({
  r,
  upload,
  ack,
  onAck,
  committing,
  onCommit,
  label,
}: {
  r: Validation;
  upload: Upload;
  ack: boolean;
  onAck: (v: boolean) => void;
  committing: boolean;
  onCommit: () => void;
  label: string;
}) {
  const canSave = r.ok && r.n_valid > 0 && (r.n_error_rows === 0 || ack);
  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat k="입력 행" v={num(r.n_input)} />
        <Stat k="유효 행" v={num(r.n_valid)} tone="success" />
        <Stat k="오류 행" v={num(r.n_error_rows)} tone={r.n_error_rows ? "danger" : undefined} />
        <Stat k="경고" v={num(r.warnings.length)} tone={r.warnings.length ? "warning" : undefined} />
      </div>
      {r.fatal.map((f) => (
        <Callout key={f} tone="danger" icon={AlertOctagon} title="저장 불가">
          {f}
        </Callout>
      ))}
      {r.warnings.map((w) => (
        <Callout key={w} tone="warning" icon={AlertTriangle}>
          {w}
        </Callout>
      ))}
      {r.error_summary.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-[13px] font-semibold">오류 요약</h4>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                download(`/api/data/uploads/${upload.upload_id}/errors.csv`, undefined, `errors_${r.entity}.csv`).catch((e) =>
                  toast.error((e as Error).message),
                )
              }
            >
              <Download className="size-3.5" /> 오류 행 내려받기
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {r.error_summary.map((s) => (
              <span key={`${s.column}-${s.message}`} className="inline-flex items-center gap-1.5 rounded-md border border-danger/20 bg-danger/[0.05] px-2 py-1 text-[12px]">
                <span className="font-mono text-[11.5px]">{s.column}</span>
                <span className="text-muted-foreground">{s.message}</span>
                <b className="text-danger tabular">{num(s.count)}</b>
              </span>
            ))}
          </div>
          <DataTable data={r.errors} columns={ERR_COLS} rowKey={(x) => `${x.row}-${x.column}-${x.message}`} height={240} ariaLabel="오류 상세" />
          <p className="text-[11.5px] text-muted-foreground">행 번호는 파일 기준입니다 (헤더 = 1행). 상위 500건 표시.</p>
        </div>
      )}
      {r.ok && r.n_valid > 0 && (
        <div className="space-y-3 border-t border-border pt-4">
          {r.n_error_rows > 0 && (
            <div className="flex items-start gap-2">
              <Checkbox id="ack" checked={ack} onCheckedChange={(v) => onAck(v === true)} className="mt-0.5" />
              <Label htmlFor="ack" className="text-[13px] font-normal leading-snug">
                오류 행 {num(r.n_error_rows)}건을 제외하고 유효 행 {num(r.n_valid)}건만 저장합니다.
              </Label>
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[12.5px] text-muted-foreground">
              {r.current_version
                ? `저장하면 ${label} v${r.current_version + 1} 이 활성화되고 v${r.current_version} 은 보존됩니다 (롤백 가능).`
                : `${label} 첫 버전(v1)으로 저장됩니다.`}{" "}
              단일 트랜잭션 — 실패 시 전체 취소.
            </p>
            <Button onClick={onCommit} disabled={!canSave || committing}>
              {committing ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}
              {num(r.n_valid)}행 저장
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Done({ label, done, onAnother }: { label: string; done: Schemas["CommitOut"]; onAnother: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-success/25 bg-success/[0.05] px-6 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-success/15">
        <CheckCircle2 className="size-6 text-success" />
      </div>
      <div>
        <p className="text-base font-semibold">
          {label} v{done.version} 저장 완료
        </p>
        <p className="mt-1 text-[13px] text-muted-foreground tabular">
          {num(done.rows)}행 · dataset #{done.dataset_id} · 모든 화면에 즉시 반영됩니다
        </p>
      </div>
      <div className="mt-2 flex gap-2">
        <Button variant="outline" onClick={onAnother}>
          <ArrowLeft className="size-4" /> 다른 데이터 업로드
        </Button>
        <Button asChild>
          <Link href="/control-tower/">Control Tower 에서 보기</Link>
        </Button>
      </div>
    </div>
  );
}

function DemoReload() {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => unwrap(client.POST("/api/data/demo")),
    onSuccess: (r) => {
      qc.invalidateQueries();
      toast.success("샘플 데이터를 다시 불러왔습니다", { description: `${Object.keys(r.entities).length}개 데이터 유형 · 새 버전으로 저장` });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-kind-demo/25 bg-kind-demo/[0.05] px-4 py-3">
      <p className="text-[12.5px] text-foreground/80">샘플 워크스페이스에서는 시연용 가상 데이터를 한 번에 다시 불러올 수 있습니다.</p>
      <Button variant="outline" size="sm" onClick={() => m.mutate()} disabled={m.isPending}>
        {m.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <RotateCcw className="size-3.5" />} 샘플 데이터 다시 불러오기
      </Button>
    </div>
  );
}

function Stat({ k, v, tone }: { k: string; v: string; tone?: "success" | "danger" | "warning" }) {
  return (
    <div className="rounded-lg border border-border px-3 py-2.5">
      <p className="text-[11.5px] text-muted-foreground">{k}</p>
      <p
        className={cn(
          "mt-0.5 text-[20px] font-semibold tracking-tight tabular",
          tone === "success" && "text-success",
          tone === "danger" && "text-danger",
          tone === "warning" && "text-warning",
        )}
      >
        {v}
      </p>
    </div>
  );
}

function Callout({
  tone,
  icon: Icon,
  title,
  children,
}: {
  tone: "danger" | "warning";
  icon: typeof AlertTriangle;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role={tone === "danger" ? "alert" : undefined}
      className={cn(
        "flex items-start gap-2 rounded-lg px-3 py-2 text-[12.5px]",
        tone === "danger" ? "bg-danger/[0.07] text-foreground" : "bg-warning/[0.08] text-foreground",
      )}
    >
      <Icon className={cn("mt-px size-4 shrink-0", tone === "danger" ? "text-danger" : "text-warning")} />
      <span>
        {title && <b className="mr-1">{title} —</b>}
        {children}
      </span>
    </div>
  );
}
