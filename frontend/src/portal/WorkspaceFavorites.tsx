import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { type Module } from "../shared/api";
import { ErrorNotice, Loading, PageTitle } from "../shared/components";
import { useFavorites } from "../shared/favorites";
import { MenuIcon } from "../shared/MenuIcon";
import {
  menuByKey,
  menuCatalog,
  menuSolutions,
  type Menu,
} from "../shared/menuCatalog";
import "./WorkspaceFavorites.css";

export function WorkspaceFavorites({
  modules,
  disabled,
}: {
  modules: Module[];
  disabled: boolean;
}) {
  const favorites = useFavorites();
  const [filter, setFilter] = useState("all");
  const [editor, setEditor] = useState<string>();
  const [params, setParams] = useSearchParams();
  const requested = params.get("menus");
  useEffect(() => {
    if (
      requested &&
      favorites.data &&
      menuSolutions.some((s) => s.key === requested)
    )
      setEditor(requested);
  }, [requested, favorites.data]);
  const selected = (favorites.data?.menuIds ?? [])
    .map((key) => menuByKey.get(key)!)
    .filter(Boolean);
  const visible = selected.filter(
    (m) => filter === "all" || m.module === filter,
  );
  const unavailable = (menu: Menu) =>
    modules.some((m) => m.moduleKey === menu.module && !m.enabled);
  const blocked =
    disabled || favorites.loading || favorites.pending || !favorites.data;
  function close() {
    setEditor(undefined);
    if (requested) {
      const next = new URLSearchParams(params);
      next.delete("menus");
      setParams(next, { replace: true });
    }
  }
  return (
    <div className="workspace-favorites">
      <PageTitle
        id="P-06"
        title="내 공간"
        subtitle="자주 사용하는 업무 메뉴만 모아 나만의 작업 공간을 구성하세요."
        actions={
          <>
            <button
              className="secondary"
              disabled={blocked || favorites.uncertain}
              onClick={() => setEditor("gw")}
            >
              순서·구성 편집
            </button>
            <button
              disabled={blocked || favorites.uncertain}
              onClick={() => setEditor("gw")}
            >
              <MenuIcon kind="plus" /> 메뉴 추가
            </button>
          </>
        }
      />
      <ErrorNotice
        error={favorites.error}
        retry={favorites.pending ? undefined : () => void favorites.reload()}
      />
      {favorites.loading && (
        <Loading label="내 메뉴 구성을 불러오고 있습니다." />
      )}
      <section
        className="favorite-menu-section"
        aria-label="자주 사용하는 메뉴"
      >
        <div className="favorite-filter-bar">
          <div className="favorite-filters" aria-label="즐겨찾기 솔루션 필터">
            <button
              aria-pressed={filter === "all"}
              onClick={() => setFilter("all")}
            >
              전체
            </button>
            {menuSolutions.map((s) => (
              <button
                key={s.key}
                aria-pressed={filter === s.key}
                onClick={() => setFilter(s.key)}
              >
                {s.name}
              </button>
            ))}
          </div>
          <p className="favorite-count">
            <MenuIcon kind="grid" /> 선택한 메뉴 {selected.length}개
          </p>
        </div>
        <h2>자주 사용하는 메뉴</h2>
        <p className="favorite-description">
          카드를 선택하면 해당 업무로 바로 이동합니다.
        </p>
        {!favorites.loading && favorites.data && visible.length === 0 && (
          <p className="favorite-empty">
            {filter === "all"
              ? "등록된 메뉴가 없습니다. 자주 쓰는 메뉴를 추가해 보세요."
              : "이 솔루션에 등록된 메뉴가 없습니다."}
          </p>
        )}
        <div className="favorite-cards">
          {visible.map((menu) => (
            <Link
              key={menu.key}
              to={menu.to}
              aria-label={`${menu.label} · ${menu.solution} ${menu.group}${unavailable(menu) ? " · 앱 사용 꺼짐" : ""}`}
              className={`favorite-card favorite-tone-${menu.module}`}
            >
              <span className="favorite-icon">
                <MenuIcon menu={menu} />
              </span>
              <strong>{menu.label}</strong>
              <span>
                {menu.solution} · {menu.group}
              </span>
              {unavailable(menu) && (
                <small className="favorite-off">앱 사용 꺼짐</small>
              )}
            </Link>
          ))}
          <button
            className="favorite-add-card"
            disabled={blocked || favorites.uncertain}
            onClick={() => setEditor(filter === "all" ? "gw" : filter)}
          >
            <span>
              <MenuIcon kind="plus" />
            </span>
            메뉴 추가
          </button>
        </div>
      </section>
      <div className="favorite-support">
        <section className="favorite-tip">
          <h2>업무 흐름대로 묶어보세요.</h2>
          <p>
            솔루션이 달라도 함께 사용하는 메뉴를 한 공간에 두면 화면을 오가는
            시간을 줄일 수 있습니다.
          </p>
          <p>같은 구성으로 각 솔루션의 사이드바도 사용할 수 있습니다.</p>
        </section>
        <section className="favorite-recent">
          <h2>최근 사용한 메뉴</h2>
          {favorites.recent.length ? (
            <ul>
              {favorites.recent.map((key) => {
                const menu = menuByKey.get(key)!;
                return (
                  <li key={key}>
                    <Link to={menu.to}>
                      {menu.label}
                      <span>{menu.solution}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p>업무 화면을 사용하면 여기에 표시됩니다.</p>
          )}
          <small>최근 사용 내역은 이 브라우저에 보관됩니다.</small>
        </section>
      </div>
      {editor && favorites.data && (
        <MenuEditor
          initialSolution={editor}
          modules={modules}
          onClose={close}
        />
      )}
    </div>
  );
}

function MenuEditor({
  initialSolution,
  modules,
  onClose,
}: {
  initialSolution: string;
  modules: Module[];
  onClose: () => void;
}) {
  const favorites = useFavorites();
  const [draft, setDraft] = useState(favorites.data!.menuIds);
  const [solution, setSolution] = useState(initialSolution);
  const [search, setSearch] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const blocked = favorites.pending || favorites.loading || favorites.uncertain;
  const choices = menuCatalog.filter(
    (m) =>
      m.module === solution &&
      `${m.label} ${m.id} ${m.group}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const element = dialog.current!;
    if (element.showModal) element.showModal();
    else element.setAttribute("open", "");
    return () => {
      element.close?.();
      opener?.focus();
    };
  }, []);
  function toggle(key: string) {
    setDraft((old) =>
      old.includes(key) ? old.filter((id) => id !== key) : [...old, key],
    );
  }
  function move(key: string, index: number) {
    setDraft((old) => {
      const next = old.filter((id) => id !== key);
      next.splice(index, 0, key);
      return next;
    });
    setAnnouncement(
      `${menuByKey.get(key)!.label}을 ${index + 1}번째로 이동했습니다.`,
    );
  }
  async function submit() {
    if (await favorites.save(draft, favorites.data!.sidebarMode)) onClose();
  }
  async function reload() {
    const value = await favorites.reload();
    if (value) {
      setDraft(value.menuIds);
      setAnnouncement("최신 메뉴 구성을 불러왔습니다.");
    }
  }
  return (
    <dialog
      ref={dialog}
      className="menu-picker"
      aria-labelledby="menu-picker-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!blocked) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key !== "Tab") return;
        const controls = Array.from(
          dialog.current!.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]',
          ),
        );
        const first = controls[0],
          last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }}
    >
      <header className="menu-picker-head">
        <div>
          <h2 id="menu-picker-title">내 공간에 메뉴 추가</h2>
          <p>솔루션별 하위 메뉴를 선택해 바로가기를 구성하세요.</p>
        </div>
        <button
          className="favorite-icon-button"
          aria-label="메뉴 편집 닫기"
          disabled={blocked}
          onClick={onClose}
        >
          <MenuIcon kind="close" />
        </button>
      </header>
      <div className="menu-picker-body">
        <nav className="menu-picker-solutions" aria-label="메뉴 선택 솔루션">
          <h3>솔루션</h3>
          {menuSolutions.map((s) => (
            <button
              key={s.key}
              aria-pressed={s.key === solution}
              disabled={blocked}
              onClick={() => {
                setSolution(s.key);
                setSearch("");
              }}
            >
              {s.name}
              <span>
                {draft.filter((key) => key.startsWith(`${s.key}:`)).length}
              </span>
            </button>
          ))}
        </nav>
        <section className="menu-picker-choices" aria-label="등록할 메뉴 선택">
          <p className="favorite-description">
            {solution.toUpperCase()} 솔루션
          </p>
          <h3>추가할 메뉴를 선택하세요</h3>
          {modules.some((m) => m.moduleKey === solution && !m.enabled) && (
            <p className="notice">
              앱 사용이 꺼져 있습니다. 등록한 메뉴는 보존되며 앱을 켜면 사용할
              수 있습니다.
            </p>
          )}
          <label className="menu-search">
            메뉴 검색
            <input
              value={search}
              disabled={blocked}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="메뉴 이름·화면 ID·분류"
            />
          </label>
          {choices.length === 0 && <p>검색 결과가 없습니다.</p>}
          {[...new Set(choices.map((m) => m.group))]
            .sort((a, b) => {
              if (solution !== "gw") return 0;
              const order = ["전자결재", "게시판", "기준정보", "협업"];
              return order.indexOf(a) - order.indexOf(b);
            })
            .map((group) => (
              <section className="menu-picker-group" key={group}>
                <h4>{group}</h4>
                <div>
                  {choices
                    .filter((m) => m.group === group)
                    .map((menu) => (
                      <label className="menu-choice" key={menu.key}>
                        <input
                          type="checkbox"
                          checked={draft.includes(menu.key)}
                          disabled={blocked}
                          onChange={() => toggle(menu.key)}
                        />
                        <span
                          className={`menu-choice-icon favorite-tone-${menu.module}`}
                        >
                          <MenuIcon menu={menu} />
                        </span>
                        <span>
                          <strong>{menu.label}</strong>
                          <small>{menu.id}</small>
                        </span>
                      </label>
                    ))}
                </div>
              </section>
            ))}
        </section>
        <section className="menu-picker-selected" aria-label="선택한 메뉴 순서">
          <div className="menu-selected-title">
            <h3>선택한 메뉴</h3>
            <span>{draft.length}</span>
          </div>
          <p className="menu-order-hint">
            끌어서 옮기거나 위·아래 버튼으로 순서를 바꾸세요.
          </p>
          <ol>
            {draft.map((key, index) => {
              const menu = menuByKey.get(key)!;
              return (
                <li
                  key={key}
                  draggable={!blocked}
                  onDragStart={(e) => e.dataTransfer.setData("text/plain", key)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const from = e.dataTransfer.getData("text/plain");
                    if (!blocked && from !== key && draft.includes(from))
                      move(from, index);
                  }}
                >
                  <span className="menu-order">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <strong>{menu.label}</strong>
                    <small>
                      {menu.solution} · {menu.group}
                    </small>
                  </div>
                  <button
                    className="favorite-icon-button"
                    aria-label={`${menu.label} 제거`}
                    disabled={blocked}
                    onClick={() => toggle(key)}
                  >
                    <MenuIcon kind="close" />
                  </button>
                  <div className="menu-order-actions">
                    <button
                      className="favorite-icon-button"
                      aria-label={`${menu.label} 위로 이동`}
                      disabled={blocked || index === 0}
                      onClick={() => move(key, index - 1)}
                    >
                      <MenuIcon kind="up" />
                    </button>
                    <button
                      className="favorite-icon-button"
                      aria-label={`${menu.label} 아래로 이동`}
                      disabled={blocked || index === draft.length - 1}
                      onClick={() => move(key, index + 1)}
                    >
                      <MenuIcon kind="down" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ol>
          {draft.length === 0 && (
            <p className="favorite-empty">왼쪽에서 사용할 메뉴를 선택하세요.</p>
          )}
        </section>
      </div>
      <footer className="menu-picker-foot">
        <div>
          <p>선택한 메뉴는 언제든지 다시 편집할 수 있습니다.</p>
          <p role="status" className="sr-only">
            {announcement}
          </p>
          <ErrorNotice
            error={favorites.error}
            retry={favorites.pending ? undefined : () => void submit()}
          />
          {!!favorites.error && (
            <button
              className="link-button"
              disabled={favorites.pending}
              onClick={() => void reload()}
            >
              최신 구성 불러오기
            </button>
          )}
        </div>
        <div className="actions">
          <button className="secondary" disabled={blocked} onClick={onClose}>
            취소
          </button>
          <button
            disabled={favorites.pending || favorites.loading}
            onClick={() => void submit()}
          >
            {favorites.pending
              ? "저장 중…"
              : favorites.uncertain
                ? "동일 요청 다시 적용"
                : "내 공간에 적용"}
          </button>
        </div>
      </footer>
    </dialog>
  );
}
