// 실적 확정 폼 — M-05 공정 실행과 M-07 실적 확정이 같이 쓴다. 확정하면 공정이 끝난다(TX-02).
import { useState, type FormEvent } from "react";
import { Field } from "../shared/components";
import type { useSend } from "./common";

export function ResultForm({
  executionId,
  title,
  inputQty,
  unit,
  sequenceNo,
  send,
  pending,
  errors,
  onClose,
}: {
  executionId: number;
  title: string;
  inputQty: string | null;
  unit: string;
  sequenceNo: number;
  send: ReturnType<typeof useSend>["send"];
  pending: boolean;
  errors: Record<string, string>;
  onClose: () => void;
}) {
  const [good, setGood] = useState("");
  const [defect, setDefect] = useState("0");
  const [reason, setReason] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const ok = await send(`/executions/${executionId}/result`, "POST", {
      goodQty: good.trim(),
      defectQty: defect.trim() || "0",
      defectReason: reason.trim() || null,
    });
    if (ok) onClose();
  }

  return (
    <form
      className="panel"
      aria-label="실적 확정"
      onSubmit={(e) => void submit(e)}
    >
      <h2>{title}</h2>
      <p className="muted">
        {inputQty !== null &&
          `투입 ${Number(inputQty).toLocaleString()} ${unit}${sequenceNo === 1 ? " (지시 수량)" : " (직전 공정 양품)"}. `}
        양품 + 불량 = 투입이어야 하고, 확정 후에는 고칠 수 없습니다. 품질 검사는
        QMS 영역으로 범위에서 제외했으므로 작업자가 직접 판정합니다.
      </p>
      <Field
        label="양품"
        value={good}
        required
        inputMode="decimal"
        error={errors.goodQty}
        onChange={(e) => setGood(e.target.value)}
      />
      <Field
        label="불량"
        value={defect}
        inputMode="decimal"
        error={errors.defectQty}
        onChange={(e) => setDefect(e.target.value)}
      />
      <Field
        label="불량 사유"
        value={reason}
        maxLength={300}
        required={Number(defect) > 0}
        error={errors.defectReason}
        onChange={(e) => setReason(e.target.value)}
      />
      <div className="form-actions">
        <button type="submit" disabled={pending}>
          확정
        </button>
        <button type="button" className="link-button" onClick={onClose}>
          닫기
        </button>
      </div>
    </form>
  );
}
