"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Lock } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { BrandMark } from "@/components/app/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { client, unwrap } from "@/lib/api";

const schema = z.object({ code: z.string().min(1, "접근 코드를 입력하세요.").max(200) });

function safeNext(): string {
  const n = new URLSearchParams(window.location.search).get("next") ?? "/control-tower/";
  return n.startsWith("/") && !n.startsWith("//") ? n : "/control-tower/";
}

function LoginForm() {
  const status = useQuery({ queryKey: ["auth"], queryFn: () => unwrap(client.GET("/api/auth/status")) });
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { code: "" } });

  useEffect(() => {
    if (status.data && (!status.data.access_code_required || status.data.authenticated)) window.location.replace(safeNext());
  }, [status.data]);

  const onSubmit = form.handleSubmit(async ({ code }) => {
    setServerError(null);
    const { error, response } = await client.POST("/api/auth/login", { body: { code } });
    if (response.ok) {
      window.location.replace(safeNext());
      return;
    }
    setServerError((error as { detail?: string })?.detail ?? "로그인에 실패했습니다.");
    form.resetField("code");
    form.setFocus("code");
  });

  const locked = status.data?.locked;
  return (
    <div className="flex min-h-svh items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <BrandMark className="size-10" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight">LogisRisk</h1>
            <p className="mt-1 text-[13px] text-muted-foreground">물류·유통 운영 분석 플랫폼</p>
          </div>
        </div>
        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-border bg-card p-6 shadow-card" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="code" className="text-[13px]">
              접근 코드
            </Label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-subtle-foreground" />
              <Input
                id="code"
                type="password"
                autoComplete="current-password"
                autoFocus
                className="h-10 pl-8"
                aria-invalid={!!form.formState.errors.code || !!serverError}
                aria-describedby="code-help"
                disabled={locked}
                {...form.register("code")}
              />
            </div>
            <p id="code-help" className="text-[12px] text-muted-foreground">
              관리자에게 받은 공용 접근 코드를 입력하세요.
            </p>
            {(form.formState.errors.code || serverError || locked) && (
              <p role="alert" className="text-[12.5px] font-medium text-danger">
                {locked ? "시도 횟수를 초과했습니다. 잠시 후 다시 시도하세요." : (form.formState.errors.code?.message ?? serverError)}
              </p>
            )}
          </div>
          <Button type="submit" className="h-10 w-full" disabled={form.formState.isSubmitting || locked}>
            {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />} 입장
          </Button>
        </form>
        <p className="mt-4 text-center text-[11.5px] text-subtle-foreground">
          접근 코드는 공개 배포 환경의 최소 보호 장치이며 개인 계정(SSO)을 대체하지 않습니다.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
