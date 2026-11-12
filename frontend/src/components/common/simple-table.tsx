import { num } from "@/lib/format";

/** 열 이름을 그대로 쓰는 작은 표 (미배정 배송지·대체 센터 목록 등) */
export function SimpleTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Object.keys(rows[0] ?? {});
  return (
    <div className="max-h-72 overflow-auto rounded-lg border border-border">
      <table className="w-full text-body">
        <thead className="sticky top-0 bg-muted text-small text-muted-foreground">
          <tr>
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-1.5 text-left font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {cols.map((c) => (
                <td key={c} className="whitespace-nowrap px-3 py-1.5">
                  {typeof r[c] === "number" ? num(r[c] as number, Number.isInteger(r[c]) ? 0 : 1) : String(r[c] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
