// FS-040 런처 평가: 타일 아래 한 줄 평점 + 오른쪽 패널(최근 한줄평·별점 입력). 평점은 보조 정보라
// 불러오지 못해도 런처는 그대로 쓴다.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import {
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  useDiscardGuard,
} from "../shared/components";

export type ReviewSummary = {
  moduleKey: string;
  average: number;
  count: number;
  reviewed: boolean;
};
type Review = {
  nickname: string;
  rating: number;
  comment: string;
  createdAt: string;
};

export function useReviewSummary(generationId?: number) {
  const [summary, setSummary] = useState<ReviewSummary[]>([]);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    api<ReviewSummary[]>("/reviews/summary")
      .then((r) => {
        if (active && Array.isArray(r.data)) setSummary(r.data);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [generationId, reload]);
  return [summary, () => setReload((n) => n + 1)] as const;
}

export function RatingLine({
  summary,
  label,
  onOpen,
}: {
  summary?: ReviewSummary;
  label: string;
  onOpen: () => void;
}) {
  const count = summary?.count ?? 0;
  return (
    <button
      type="button"
      className="launcher-rating"
      aria-label={
        count
          ? `${label} 평점 ${summary!.average.toFixed(1)}, 후기 ${count}건 보기`
          : `${label} 평가 남기기`
      }
      onClick={onOpen}
    >
      {count ? (
        <>
          <span aria-hidden="true">★</span> {summary!.average.toFixed(1)} · 후기{" "}
          {count}
        </>
      ) : (
        "평가 모으는 중"
      )}
    </button>
  );
}

function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  return (error.error.details?.fields as Record<string, string>) ?? {};
}

export function ReviewPanel({
  moduleKey,
  label,
  summary,
  onClose,
  onSaved,
}: {
  moduleKey: string;
  label: string;
  summary?: ReviewSummary;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { session } = useSession();
  const guest = session?.actorKind === "GUEST";
  const keys = useRef(new MutationKeys());
  const [reviews, setReviews] = useState<Review[]>();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState<unknown>();
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const guard = useDiscardGuard(!done && (rating > 0 || comment !== ""));
  useEffect(() => {
    api<Review[]>(`/reviews?moduleKey=${moduleKey}`)
      .then((r) => setReviews(r.data))
      .catch(setError);
  }, [moduleKey, done]);
  const reviewed = done || summary?.reviewed;
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (saving) return;
    if (!rating) {
      setError(
        new ApiError(400, {
          code: "VALIDATION_FAILED",
          message: "별점을 고르세요.",
          details: { fields: { rating: "별점을 고르세요." } },
        }),
      );
      return;
    }
    const operation = `review:${moduleKey}`;
    setSaving(true);
    setError(undefined);
    try {
      await api("/reviews", {
        method: "POST",
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
        body: { moduleKey, rating, comment, ...(guest ? { nickname } : {}) },
      });
      keys.current.complete(operation);
      setDone(true);
      onSaved();
    } catch (err) {
      // 입력을 고쳐 다시 보내면 본문이 달라지므로 새 키를 쓴다. 응답 불확실(0)만 같은 키로 재시도한다.
      if (!(err instanceof ApiError && err.status === 0))
        keys.current.complete(operation);
      setError(err);
    } finally {
      setSaving(false);
    }
  }
  const fields = fieldErrors(error);
  return (
    <FormPanel
      title={`${label} 평가`}
      onClose={onClose}
      onSubmit={submit}
      guard={guard}
      actions={
        reviewed ? (
          <button type="button" className="secondary" onClick={onClose}>
            닫기
          </button>
        ) : (
          <>
            <button type="submit" disabled={saving}>
              {saving ? "보내는 중" : "평가 남기기"}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => guard.guard(onClose)}
            >
              취소
            </button>
          </>
        )
      }
    >
      <p className="review-score">
        {summary?.count ? (
          <>
            <span aria-hidden="true">★</span> {summary.average.toFixed(1)}
            <small> · 후기 {summary.count}건</small>
          </>
        ) : (
          <small>아직 평가가 없습니다. 첫 평가를 남겨 주세요.</small>
        )}
      </p>
      <ErrorNotice error={error} />
      {reviewed ? (
        <p className="review-done" role="status">
          {done
            ? "평가를 남겼습니다. 고맙습니다."
            : "이 솔루션은 이미 평가했습니다."}
        </p>
      ) : (
        <>
          <fieldset className="review-stars">
            <legend>별점</legend>
            {[1, 2, 3, 4, 5].map((n) => (
              <label key={n} className={n <= rating ? "on" : ""}>
                <input
                  type="radio"
                  name="rating"
                  value={n}
                  checked={rating === n}
                  onChange={() => setRating(n)}
                  aria-label={`${n}점`}
                />
                <span aria-hidden="true">★</span>
              </label>
            ))}
            {fields.rating && <small role="alert">{fields.rating}</small>}
          </fieldset>
          {guest && (
            <Field
              label="별칭"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              maxLength={20}
              placeholder="실명 대신 별칭 · 공개 표시"
              error={fields.nickname}
            />
          )}
          <Field
            label="한줄평"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={100}
            placeholder="2~100자"
            error={fields.comment}
          />
        </>
      )}
      <h3 className="review-recent-title">최근 한줄평</h3>
      {!reviews ? (
        <Loading />
      ) : reviews.length === 0 ? (
        <p className="muted">아직 한줄평이 없습니다.</p>
      ) : (
        <ul className="review-list">
          {reviews.map((r, i) => (
            <li key={`${r.createdAt}-${i}`}>
              <span className="review-rating" aria-label={`${r.rating}점`}>
                {"★".repeat(r.rating)}
                <span className="off">{"★".repeat(5 - r.rating)}</span>
              </span>
              <p>{r.comment}</p>
              <small>
                {r.nickname} · {r.createdAt.slice(0, 10)}
              </small>
            </li>
          ))}
        </ul>
      )}
    </FormPanel>
  );
}
