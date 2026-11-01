// F-14 상세 — TOU 시간대 구간표 (DSN-15 F05·Q1)
// 구간은 통째로 저장한다. 한 줄씩 고치면 하루를 못 덮는 중간 상태가 생긴다.
import { useEffect, useState } from "react";
import { api } from "../shared/api";
import { fieldErrors } from "../shared/hooks";
import { DetailPanel, ErrorNotice, Field } from "../shared/components";
import {
  BAND_LABEL,
  DAY_KIND_LABEL,
  SEASON_LABEL,
  type Band,
  type Tariff,
} from "./Tariffs";

const SEASONS = ["SUMMER", "SPRING_FALL", "WINTER"] as const;
const DAY_KINDS = ["WEEKDAY", "SATURDAY", "HOLIDAY"] as const;
const BANDS = ["OFF_PEAK", "MID", "PEAK"] as const;

const NEW_ROW: Band = {
  season: "SUMMER",
  dayKind: "WEEKDAY",
  hourFrom: 0,
  hourTo: 24,
  loadBand: "MID",
  rate: "",
};

/** 3계절 × 3요일을 하루 한 구간으로 채운 뼈대. 여기서 시간을 쪼개 나간다. */
function skeleton(rate: string): Band[] {
  return SEASONS.flatMap((season) =>
    DAY_KINDS.map((dayKind) => ({ ...NEW_ROW, season, dayKind, rate })),
  );
}

export function TariffBandsPanel({
  tariff,
  onClose,
  csrfToken,
}: {
  tariff: Tariff;
  onClose: () => void;
  csrfToken: string;
}) {
  const [bands, setBands] = useState<Band[]>();
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState<string>();
  const [pending, setPending] = useState(false);
  const [draft, setDraft] = useState<Band>(NEW_ROW);

  useEffect(() => {
    api<Tariff & { bands: Band[] }>(`/api/v1/fems/tariffs/${tariff.id}`)
      .then((r) => setBands(r.data.bands))
      .catch(setError);
  }, [tariff.id]);

  async function save(rows: Band[]) {
    setPending(true);
    setError(undefined);
    setSaved(undefined);
    try {
      const response = await api<{ bands: Band[] }>(
        `/api/v1/fems/tariffs/${tariff.id}/bands`,
        {
          method: "PUT",
          body: {
            bands: rows.map((b) => ({
              season: b.season,
              dayKind: b.dayKind,
              hourFrom: b.hourFrom,
              hourTo: b.hourTo,
              loadBand: b.loadBand,
              rate: b.rate,
            })),
          },
          csrf: csrfToken,
          key: `bands-${tariff.id}-${Date.now()}`,
        },
      );
      setBands(response.data.bands);
      setSaved(`구간 ${response.data.bands.length}개를 저장했습니다.`);
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }

  const rows = bands ?? [];
  const fieldError = fieldErrors(error).bands;

  return (
    <DetailPanel
      wide
      title={`${tariff.tariffCode} 시간대 구간표`}
      onClose={onClose}
      actions={
        <>
          <button
            type="button"
            disabled={pending || rows.length === 0}
            onClick={() => void save(rows)}
          >
            구간표 저장
          </button>
          <button
            type="button"
            className="secondary"
            disabled={pending}
            onClick={() => setBands(skeleton(draft.rate || "0"))}
          >
            9칸 뼈대 채우기
          </button>
        </>
      }
    >
      <ErrorNotice error={fieldError ? undefined : error} />
      {fieldError && (
        <p className="field-error" role="alert">
          {fieldError}
        </p>
      )}
      {saved && <p role="status">{saved}</p>}
      <p className="muted" role="note">
        계절·요일마다 <strong>0~24시를 빈틈·겹침 없이</strong> 덮어야
        저장됩니다. 3계절 × 3요일이 모두 있어야 합니다.
      </p>
      <div className="field-row">
        <label>
          계절
          <select
            value={draft.season}
            onChange={(e) =>
              setDraft({ ...draft, season: e.target.value as Band["season"] })
            }
          >
            {SEASONS.map((s) => (
              <option key={s} value={s}>
                {SEASON_LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        <label>
          요일
          <select
            value={draft.dayKind}
            onChange={(e) =>
              setDraft({ ...draft, dayKind: e.target.value as Band["dayKind"] })
            }
          >
            {DAY_KINDS.map((d) => (
              <option key={d} value={d}>
                {DAY_KIND_LABEL[d]}
              </option>
            ))}
          </select>
        </label>
        <Field
          label="시작 시"
          inputMode="numeric"
          value={String(draft.hourFrom)}
          onChange={(e) =>
            setDraft({ ...draft, hourFrom: Number(e.target.value || 0) })
          }
        />
        <Field
          label="끝 시"
          inputMode="numeric"
          value={String(draft.hourTo)}
          onChange={(e) =>
            setDraft({ ...draft, hourTo: Number(e.target.value || 0) })
          }
        />
        <label>
          부하 구분
          <select
            value={draft.loadBand}
            onChange={(e) =>
              setDraft({
                ...draft,
                loadBand: e.target.value as Band["loadBand"],
              })
            }
          >
            {BANDS.map((b) => (
              <option key={b} value={b}>
                {BAND_LABEL[b]}
              </option>
            ))}
          </select>
        </label>
        <Field
          label="요율 (KRW)"
          inputMode="decimal"
          value={draft.rate}
          onChange={(e) => setDraft({ ...draft, rate: e.target.value })}
        />
        <button
          type="button"
          className="secondary"
          disabled={!draft.rate.trim()}
          onClick={() => setBands([...rows, { ...draft }])}
        >
          구간 추가
        </button>
      </div>
      <div className="table-scroll section-block">
        <table>
          <caption>시간대 구간 {rows.length}개</caption>
          <thead>
            <tr>
              <th scope="col">계절</th>
              <th scope="col">요일</th>
              <th scope="col">시간</th>
              <th scope="col">부하</th>
              <th scope="col" className="num">
                요율
              </th>
              <th scope="col">관리</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((band, index) => (
              <tr key={`${band.season}-${band.dayKind}-${band.hourFrom}`}>
                <td>{SEASON_LABEL[band.season]}</td>
                <td>{DAY_KIND_LABEL[band.dayKind]}</td>
                <td>
                  {band.hourFrom}~{band.hourTo}시
                </td>
                <td>{BAND_LABEL[band.loadBand]}</td>
                <td className="num">{Number(band.rate).toLocaleString()}</td>
                <td>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setBands(rows.filter((_, i) => i !== index))}
                  >
                    빼기
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && (
        <p className="muted">
          구간이 없습니다. 요율을 적고 <strong>9칸 뼈대 채우기</strong>로
          시작하세요.
        </p>
      )}
    </DetailPanel>
  );
}
