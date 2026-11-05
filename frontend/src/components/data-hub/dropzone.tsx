"use client";

import { FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

const MAX = 100 * 1024 * 1024;

export function Dropzone({ onFile, busy, label }: { onFile: (f: File) => void; busy?: boolean; label: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const accept = (f: File | undefined) => {
    if (!f) return;
    if (!/\.(csv|xlsx|xls)$/i.test(f.name)) return setErr("CSV 또는 Excel(.xlsx) 파일만 올릴 수 있습니다.");
    if (f.size > MAX) return setErr("파일이 100MB 를 넘습니다.");
    setErr(null);
    onFile(f);
  };

  return (
    <div>
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          accept(e.dataTransfer.files?.[0]);
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
          over ? "border-primary bg-primary/[0.05]" : "border-border-strong bg-muted/30 hover:border-primary/50 hover:bg-muted/50",
          busy && "pointer-events-none opacity-70",
        )}
        aria-label={`${label} 파일 선택`}
      >
        <div className="flex size-11 items-center justify-center rounded-full bg-card shadow-sm ring-1 ring-border">
          {busy ? <Loader2 className="size-5 animate-spin text-primary" /> : <UploadCloud className="size-5 text-primary" />}
        </div>
        <p className="text-[14px] font-medium">
          {busy ? "파일 읽는 중…" : <>{label} 파일을 끌어다 놓거나 <span className="text-primary">찾아보기</span></>}
        </p>
        <p className="flex items-center gap-1 text-[12px] text-muted-foreground">
          <FileSpreadsheet className="size-3.5" /> CSV(UTF-8·CP949) · Excel(.xlsx) · 최대 100MB
        </p>
      </button>
      <input
        ref={input}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          accept(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {err && (
        <p role="alert" className="mt-2 text-[12.5px] font-medium text-danger">
          {err}
        </p>
      )}
    </div>
  );
}
