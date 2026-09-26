// F-12 계측기·채널 — 계측기 목록과 선택한 계측기의 채널을 함께 관리하는 마스터-디테일 (FS-018l)
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  type Column,
  RevealAnchor,
} from "../shared/components";
import { MasterOrder } from "./EnergySources";

const BASE = "/api/v1/fems/meters";

export type Channel = {
  id: number;
  meterId: number;
  energySourceId: number;
  channelCode: string;
  name: string;
  measurementKind: "CUMULATIVE" | "INSTANT";
  unit: string;
  multiplier: string;
  isActive: boolean;
  observed: boolean;
};

export type Meter = {
  id: number;
  siteId: number;
  locationId: number;
  parentMeterId: number | null;
  equipmentId: number | null;
  meterCode: string;
  name: string;
  scopeKind: "factory" | "site_total";
  channelCount: number;
  observed: boolean;
  channels: Channel[];
};

type Named = { id: number; name: string };
type Location = Named & { locationCode: string };
type Equipment = Named & { equipmentCode: string; locationId: number };
type Source = Named & {
  sourceCode: string;
  sourceKind: string;
  measureUnit: string;
};

type MeterDraft = {
  meterCode: string;
  name: string;
  locationId: number;
  equipmentId: number | null;
  parentMeterId: number | null;
  scopeKind: Meter["scopeKind"];
};
type ChannelDraft = {
  channelCode: string;
  name: string;
  energySourceId: number;
  measurementKind: Channel["measurementKind"];
  unit: string;
  multiplier: string;
  isActive: boolean;
};

const SCOPES = { factory: "공정·설비", site_total: "사업장 전체" };
const KINDS = { CUMULATIVE: "누적", INSTANT: "순시" };

function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}

/** 수정 시 바뀐 값만 보낸다. */
function changed<T extends object>(draft: T, current: object) {
  return Object.fromEntries(
    Object.entries(draft).filter(
      ([k, v]) => (current as Record<string, unknown>)[k] !== v,
    ),
  );
}

export function Meters() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [meters, setMeters] = useState<Meter[]>();
  const [locations, setLocations] = useState<Location[]>([]);
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [selectedId, setSelectedId] = useState<number>();
  const [editingMeter, setEditingMeter] = useState<Meter | null>(null);
  const [meterDraft, setMeterDraft] = useState<MeterDraft>();
  const [editingChannel, setEditingChannel] = useState<Channel | null>(null);
  const [channelDraft, setChannelDraft] = useState<ChannelDraft>();
  const [saveError, setSaveError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<string>();
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;
    setLoadError(undefined);
    Promise.all([
      api<Meter[]>(BASE, { signal }),
      api<Location[]>("/api/v1/fems/locations", { signal }),
      api<Equipment[]>("/api/v1/fems/equipments?limit=200", { signal }),
      api<Source[]>("/api/v1/fems/energy-sources?limit=200", { signal }),
    ])
      .then(([m, l, e, s]) => {
        setMeters(m.data);
        setLocations(l.data);
        setEquipments(e.data);
        setSources(s.data);
      })
      .catch((e) => {
        if (signal.aborted) return;
        setLoadError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [reload]);

  const selected = meters?.find((m) => m.id === selectedId);
  const emptyMeter = (): MeterDraft => ({
    meterCode: "",
    name: "",
    locationId: locations[0]?.id ?? 0,
    equipmentId: null,
    parentMeterId: null,
    scopeKind: "factory",
  });
  const emptyChannel = (): ChannelDraft => ({
    channelCode: "",
    name: "",
    energySourceId: sources[0]?.id ?? 0,
    measurementKind: "CUMULATIVE",
    unit: sources[0]?.measureUnit ?? "",
    multiplier: "1",
    isActive: true,
  });
  const mDraft = meterDraft ?? emptyMeter();
  const cDraft = channelDraft ?? emptyChannel();

  function editMeter(row: Meter | null) {
    setEditingMeter(row);
    setMeterDraft(
      row
        ? {
            meterCode: row.meterCode,
            name: row.name,
            locationId: row.locationId,
            equipmentId: row.equipmentId,
            parentMeterId: row.parentMeterId,
            scopeKind: row.scopeKind,
          }
        : undefined,
    );
    setSaveError(undefined);
  }

  function editChannel(row: Channel | null) {
    setEditingChannel(row);
    setChannelDraft(
      row
        ? {
            channelCode: row.channelCode,
            name: row.name,
            energySourceId: row.energySourceId,
            measurementKind: row.measurementKind,
            unit: row.unit,
            multiplier: row.multiplier,
            isActive: row.isActive,
          }
        : undefined,
    );
    setSaveError(undefined);
  }

  function select(id: number | undefined) {
    setSelectedId(id);
    editChannel(null);
  }

  async function send(
    operation: string,
    path: string,
    method: string,
    body?: unknown,
  ) {
    setPending(true);
    setSaveError(undefined);
    try {
      const r = await api<Meter>(path, {
        method,
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      keys.current.complete(operation);
      setReload((n) => n + 1);
      return r;
    } catch (e) {
      if (e instanceof ApiError && e.status > 0 && e.status < 500)
        keys.current.complete(operation);
      setSaveError(e);
      if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      return undefined;
    } finally {
      setPending(false);
      setConfirmDelete(undefined);
    }
  }

  async function submitMeter(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const draft = {
      ...mDraft,
      meterCode: mDraft.meterCode.trim().toUpperCase(),
      name: mDraft.name.trim(),
    };
    const body = editingMeter ? changed(draft, editingMeter) : draft;
    if (editingMeter && !Object.keys(body).length) return;
    const op = `meter:${editingMeter?.id ?? "new"}:${JSON.stringify(body)}`;
    const r = await send(
      op,
      editingMeter ? `${BASE}/${editingMeter.id}` : BASE,
      editingMeter ? "PATCH" : "POST",
      body,
    );
    if (r) {
      editMeter(null);
      if (!editingMeter) select(r.data.id);
    }
  }

  async function submitChannel(event: FormEvent) {
    event.preventDefault();
    if (pending || !selected) return;
    const draft = {
      ...cDraft,
      channelCode: cDraft.channelCode.trim().toUpperCase(),
      name: cDraft.name.trim(),
      unit: cDraft.unit.trim(),
      multiplier: cDraft.multiplier.trim(),
    };
    const body = editingChannel ? changed(draft, editingChannel) : draft;
    if (editingChannel && !Object.keys(body).length) return;
    const path = `${BASE}/${selected.id}/channels`;
    const op = `channel:${editingChannel?.id ?? "new"}:${JSON.stringify(body)}`;
    const r = await send(
      op,
      editingChannel ? `${path}/${editingChannel.id}` : path,
      editingChannel ? "PATCH" : "POST",
      body,
    );
    if (r) editChannel(null);
  }

  if (
    loadError instanceof ApiError &&
    loadError.error.details?.reason === "MODULE_DISABLED"
  )
    return (
      <EmptyState
        reason="FEMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );

  const title = (
    <>
      <PageTitle
        id="F-12"
        title="계측기·채널"
        subtitle="계측기와 계측기가 재는 채널(에너지원·단위·배수)을 관리합니다"
        help="fems/f-12"
      />
      <MasterOrder />
    </>
  );

  if (meters && sources.length === 0)
    return (
      <>
        {title}
        <EmptyState
          reason="등록된 에너지원이 없습니다. 채널은 에너지원이 먼저 있어야 합니다."
          to="/fems/energy-sources"
          action="에너지원 화면으로"
        />
      </>
    );

  const errors = fieldErrors(saveError);
  const name = <T extends Named>(list: T[], id: number | null) =>
    id === null ? "-" : (list.find((x) => x.id === id)?.name ?? String(id));
  const meterName = (id: number | null) =>
    id === null
      ? "-"
      : (meters?.find((m) => m.id === id)?.meterCode ?? String(id));
  const deleteButtons = (key: string, onDelete: () => void) =>
    confirmDelete === key ? (
      <>
        <button
          type="button"
          className="secondary"
          disabled={pending}
          onClick={onDelete}
        >
          삭제 확정
        </button>
        <button
          type="button"
          className="link-button"
          onClick={() => setConfirmDelete(undefined)}
        >
          취소
        </button>
      </>
    ) : (
      <button
        type="button"
        className="link-button"
        onClick={() => {
          setConfirmDelete(key);
          setSaveError(undefined);
        }}
      >
        삭제
      </button>
    );

  const meterColumns: Column<Meter>[] = [
    { key: "meterCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={r.id === selectedId}
            onClick={() => select(r.id)}
          >
            채널 {r.channelCount}
          </button>
          <button
            type="button"
            className="link-button"
            onClick={() => editMeter(r)}
          >
            수정
          </button>
          {deleteButtons(`meter:${r.id}`, () => {
            void send(`delete-meter:${r.id}`, `${BASE}/${r.id}`, "DELETE");
          })}
        </span>
      ),
    },
    { key: "name", label: "이름" },
    {
      key: "parentMeterId",
      label: "상위 계측기",
      render: (r) => meterName(r.parentMeterId),
    },
    {
      key: "locationId",
      label: "공간",
      render: (r) => name(locations, r.locationId),
    },
    {
      key: "equipmentId",
      label: "설비",
      render: (r) => name(equipments, r.equipmentId),
    },
    { key: "scopeKind", label: "범위", render: (r) => SCOPES[r.scopeKind] },
  ];

  const channelColumns: Column<Channel>[] = [
    { key: "channelCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            onClick={() => editChannel(r)}
          >
            수정
          </button>
          {deleteButtons(`channel:${r.id}`, () => {
            void send(
              `delete-channel:${r.id}`,
              `${BASE}/${r.meterId}/channels/${r.id}`,
              "DELETE",
            );
          })}
        </span>
      ),
    },
    { key: "name", label: "이름" },
    {
      key: "energySourceId",
      label: "에너지원",
      render: (r) => name(sources, r.energySourceId),
    },
    {
      key: "measurementKind",
      label: "측정",
      render: (r) => `${KINDS[r.measurementKind]} · ${r.unit}`,
    },
    {
      key: "multiplier",
      label: "계기 배수",
      // 배수 오입력은 모든 하위 계산을 조용히 틀리게 만든다. 1이 아니면 눈에 띄게 둔다.
      render: (r) =>
        Number(r.multiplier) === 1 ? (
          "1"
        ) : (
          <Badge tone="warning">× {Number(r.multiplier)}</Badge>
        ),
    },
    {
      key: "isActive",
      label: "사용",
      render: (r) => (r.isActive ? "사용" : "사용 안 함"),
    },
  ];

  const meterLocked = !!editingMeter?.observed;
  const channelLocked = !!editingChannel?.observed;
  const source = sources.find((s) => s.id === cDraft.energySourceId);
  const locationEquipments = equipments.filter(
    (e) => e.locationId === mDraft.locationId,
  );

  return (
    <>
      {title}
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={loadError} retry={() => setReload((n) => n + 1)} />
      {!meters ? (
        !loadError && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={meters}
                columns={meterColumns}
                caption="계측기 목록"
                offset={0}
                total={meters.length}
                limit={meters.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 계측기가 없습니다. 우측 폼에서 첫 계측기를 등록하세요."
                    to="#meter-form"
                    action="계측기 등록"
                  />
                }
              />
            </section>
            <form
              id="meter-form"
              className="panel"
              aria-label={editingMeter ? "계측기 수정" : "계측기 등록"}
              onSubmit={(e) => void submitMeter(e)}
            >
              <h2>
                {editingMeter
                  ? `${editingMeter.meterCode} 수정`
                  : "계측기 등록"}
              </h2>
              <Field
                label="계측기 코드"
                value={mDraft.meterCode}
                required
                maxLength={40}
                pattern="[A-Z][A-Z0-9_\-]{1,39}"
                title="영문 대문자로 시작하는 2~40자 (대문자·숫자·_·-)"
                error={errors.meterCode}
                onChange={(e) =>
                  setMeterDraft({
                    ...mDraft,
                    meterCode: e.target.value.toUpperCase(),
                  })
                }
              />
              <Field
                label="계측기 이름"
                value={mDraft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) =>
                  setMeterDraft({ ...mDraft, name: e.target.value })
                }
              />
              {meterLocked && (
                <p className="muted">
                  계측값이 있는 계측기라 공간·설비·상위 계측기를 바꿀 수
                  없습니다. 바꾸려면 새 계측기를 등록하세요.
                </p>
              )}
              <div className="field">
                <label htmlFor="meter-location">공간</label>
                <select
                  id="meter-location"
                  value={mDraft.locationId}
                  disabled={meterLocked}
                  onChange={(e) =>
                    setMeterDraft({
                      ...mDraft,
                      locationId: Number(e.target.value),
                      equipmentId: null,
                    })
                  }
                >
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name} ({l.locationCode})
                    </option>
                  ))}
                </select>
                {errors.locationId && <small>{errors.locationId}</small>}
              </div>
              <div className="field">
                <label htmlFor="meter-equipment">설비</label>
                <select
                  id="meter-equipment"
                  value={mDraft.equipmentId ?? ""}
                  disabled={meterLocked}
                  onChange={(e) =>
                    setMeterDraft({
                      ...mDraft,
                      equipmentId: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">연결 안 함</option>
                  {locationEquipments.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.name} ({q.equipmentCode})
                    </option>
                  ))}
                </select>
                {errors.equipmentId && <small>{errors.equipmentId}</small>}
              </div>
              <div className="field">
                <label htmlFor="meter-parent">상위 계측기</label>
                <select
                  id="meter-parent"
                  value={mDraft.parentMeterId ?? ""}
                  disabled={meterLocked}
                  onChange={(e) =>
                    setMeterDraft({
                      ...mDraft,
                      parentMeterId: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">없음 (최상위 · 사업장 합계에 포함)</option>
                  {meters
                    .filter((m) => m.id !== editingMeter?.id)
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.meterCode} {m.name}
                      </option>
                    ))}
                </select>
                {errors.parentMeterId && <small>{errors.parentMeterId}</small>}
              </div>
              <div className="field">
                <label htmlFor="meter-scope">범위</label>
                <select
                  id="meter-scope"
                  value={mDraft.scopeKind}
                  onChange={(e) =>
                    setMeterDraft({
                      ...mDraft,
                      scopeKind: e.target.value as Meter["scopeKind"],
                    })
                  }
                >
                  {Object.entries(SCOPES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  {editingMeter ? "저장" : "등록"}
                </button>
                {editingMeter && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => editMeter(null)}
                  >
                    취소
                  </button>
                )}
              </div>
            </form>
          </div>

          <RevealAnchor when={selected} />

          {selected ? (
            <div className="master-grid">
              <section>
                <h2>
                  {selected.meterCode} {selected.name} 채널
                </h2>
                <DataTable
                  rows={selected.channels}
                  columns={channelColumns}
                  caption={`${selected.meterCode} 채널 목록`}
                  offset={0}
                  total={selected.channels.length}
                  limit={selected.channels.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason="이 계측기에 채널이 없습니다. 계측값은 채널 단위로 쌓입니다."
                      to="#channel-form"
                      action="채널 등록"
                    />
                  }
                />
              </section>
              <form
                id="channel-form"
                className="panel"
                aria-label={editingChannel ? "채널 수정" : "채널 등록"}
                onSubmit={(e) => void submitChannel(e)}
              >
                <h2>
                  {editingChannel
                    ? `${editingChannel.channelCode} 수정`
                    : "채널 등록"}
                </h2>
                <Field
                  label="채널 코드"
                  value={cDraft.channelCode}
                  required
                  maxLength={20}
                  pattern="[A-Z][A-Z0-9_\-]{1,19}"
                  title="영문 대문자로 시작하는 2~20자 (대문자·숫자·_·-)"
                  error={errors.channelCode}
                  onChange={(e) =>
                    setChannelDraft({
                      ...cDraft,
                      channelCode: e.target.value.toUpperCase(),
                    })
                  }
                />
                <Field
                  label="채널 이름"
                  value={cDraft.name}
                  required
                  maxLength={50}
                  error={errors.name}
                  onChange={(e) =>
                    setChannelDraft({ ...cDraft, name: e.target.value })
                  }
                />
                {channelLocked && (
                  <p className="muted">
                    계측값이 있는 채널이라 에너지원·측정 종류·단위를 바꿀 수
                    없습니다. 바꾸려면 새 채널을 등록하세요.
                  </p>
                )}
                <div className="field">
                  <label htmlFor="channel-source">에너지원</label>
                  <select
                    id="channel-source"
                    value={cDraft.energySourceId}
                    disabled={channelLocked}
                    onChange={(e) => {
                      const next = sources.find(
                        (s) => s.id === Number(e.target.value),
                      );
                      setChannelDraft({
                        ...cDraft,
                        energySourceId: Number(e.target.value),
                        unit:
                          cDraft.measurementKind === "CUMULATIVE"
                            ? (next?.measureUnit ?? cDraft.unit)
                            : cDraft.unit,
                      });
                    }}
                  >
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.sourceCode})
                      </option>
                    ))}
                  </select>
                  {errors.energySourceId && (
                    <small>{errors.energySourceId}</small>
                  )}
                </div>
                <div className="field">
                  <label htmlFor="channel-kind">측정 종류</label>
                  <select
                    id="channel-kind"
                    value={cDraft.measurementKind}
                    disabled={channelLocked}
                    onChange={(e) => {
                      const kind = e.target.value as Channel["measurementKind"];
                      setChannelDraft({
                        ...cDraft,
                        measurementKind: kind,
                        unit:
                          kind === "CUMULATIVE"
                            ? (source?.measureUnit ?? cDraft.unit)
                            : cDraft.unit,
                      });
                    }}
                  >
                    <option value="CUMULATIVE">누적 (기간 합계에 사용)</option>
                    <option value="INSTANT">순시 (합계에 쓰지 않음)</option>
                  </select>
                </div>
                <Field
                  label="단위"
                  value={cDraft.unit}
                  required
                  maxLength={10}
                  disabled={channelLocked}
                  error={errors.unit}
                  onChange={(e) =>
                    setChannelDraft({ ...cDraft, unit: e.target.value })
                  }
                />
                <Field
                  label="계기 배수"
                  value={cDraft.multiplier}
                  required
                  inputMode="decimal"
                  title="0보다 큰 수, 소수 6자리까지"
                  error={errors.multiplier}
                  onChange={(e) =>
                    setChannelDraft({ ...cDraft, multiplier: e.target.value })
                  }
                />
                {Number(cDraft.multiplier) !== 1 && (
                  <p className="notice" role="status">
                    계기 배수가 1이 아닙니다. 모든 계측값에 ×{" "}
                    {cDraft.multiplier}가 곱해져 합계·요금·배출량이 함께
                    바뀝니다.
                  </p>
                )}
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={cDraft.isActive}
                    onChange={(e) =>
                      setChannelDraft({ ...cDraft, isActive: e.target.checked })
                    }
                  />
                  사용
                </label>
                <div className="form-actions">
                  <button type="submit" disabled={pending}>
                    {editingChannel ? "저장" : "등록"}
                  </button>
                  {editingChannel && (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => editChannel(null)}
                    >
                      취소
                    </button>
                  )}
                </div>
              </form>
            </div>
          ) : (
            <p className="muted">
              계측기 목록에서 &quot;채널&quot;을 누르면 그 계측기의 채널을
              관리할 수 있습니다.
            </p>
          )}
        </>
      )}
    </>
  );
}
