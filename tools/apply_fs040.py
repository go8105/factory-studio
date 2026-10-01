"""FS-040: core.app_review(런처 평가)를 schema.json에 반영한다(멱등).

근거: docs/plan/런처평가_한줄평_FS-040.md 3장(D70~D74). 새 제약·관계는 목록 끝에 붙여 기존 C·R 번호를 유지한다.
"""
import json
from pathlib import Path

from apply_fs023a import c, col

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
RV = 'core.app_review'
MODULES = ['mes', 'erp', 'fems', 'qms', 'wms', 'bems', 'spc']

TABLE = dict(
    name=RV, label='런처 평가', scope='global', phase='S1', retention='초기화 보존',
    guest_cleanup='전역 운영 피드백 유지(공간 FK 없음)', sub_module='ops',
    note='FS-040 D70~D73. 솔루션별 별점·한줄평. 회원 계정당·게스트 공간당·게스트 별칭당 1회. 수정·삭제 없음',
    columns=[
        col('id', '내부 식별자', 'bigint', default='GENERATED ALWAYS AS IDENTITY'),
        col('module_key', '솔루션 키', 'varchar(24)', rule=' / '.join(MODULES)),
        col('actor_kind', '주체 유형', 'varchar(10)', rule='MEMBER / GUEST'),
        col('user_id', '회원', 'bigint', nullable=True, rule='회원만'),
        col('guest_actor_key', '게스트 주체 키', 'uuid', nullable=True, rule='게스트 공간 UUID 값 스냅샷. FK 없음(공간 정리 뒤에도 남는다)'),
        col('nickname', '표시 이름', 'varchar(20)', rule='회원 표시 이름 또는 게스트 별칭(2~20자) 스냅샷'),
        col('rating', '별점', 'smallint', rule='1~5'),
        col('comment', '한줄평', 'varchar(100)', rule='2~100자'),
        col('created_at', '등록 시각', 'timestamptz', default='now()'),
    ],
)
MODULE_CHECK = 'module_key IN (' + ', '.join(f"'{m}'" for m in MODULES) + ')'
CONSTRAINTS = [
    c(RV, 'PK', ['id'], reason='기본키'),
    c(RV, 'CHECK', ['module_key'], MODULE_CHECK, '평가 대상 솔루션'),
    c(RV, 'CHECK', ['actor_kind'], "actor_kind IN ('MEMBER', 'GUEST')", '주체 유형'),
    c(RV, 'CHECK', ['actor_kind', 'user_id', 'guest_actor_key'],
      "(actor_kind = 'MEMBER' AND user_id IS NOT NULL AND guest_actor_key IS NULL) OR "
      "(actor_kind = 'GUEST' AND user_id IS NULL AND guest_actor_key IS NOT NULL)", '주체와 식별값 일치'),
    c(RV, 'CHECK', ['rating'], 'rating BETWEEN 1 AND 5', '별점 범위'),
    c(RV, 'CHECK', ['comment'], 'char_length(btrim(comment)) >= 2', '한줄평 2자 이상'),
    c(RV, 'CHECK', ['nickname'], 'char_length(btrim(nickname)) >= 1', '표시 이름 필수'),
    c(RV, 'UK_PARTIAL', ['module_key', 'user_id'],
      'UNIQUE (module_key, user_id) WHERE user_id IS NOT NULL', '회원 계정당 솔루션별 1회(D71)'),
    c(RV, 'UK_PARTIAL', ['module_key', 'guest_actor_key'],
      'UNIQUE (module_key, guest_actor_key) WHERE guest_actor_key IS NOT NULL', '게스트 공간당 솔루션별 1회(D71)'),
    c(RV, 'UK_PARTIAL', ['module_key', 'nickname'],
      "UNIQUE (module_key, nickname) WHERE actor_kind = 'GUEST'", '게스트 같은 별칭 솔루션별 1회(D71)'),
    c(RV, 'INDEX', ['module_key', 'created_at'], reason='최근 한줄평·집계'),
    c(RV, 'INDEX', ['user_id'], reason='FK 참조 탐색'),
    c(RV, 'SERVICE/DB_POLICY', ['nickname'],
      '주체·표시 이름은 서버 인증 문맥에서 정한다(회원 = display_name 앞 20자, 게스트 = 입력 별칭 공백 제거 2~20자). '
      '수정·삭제하지 않는다. 별칭은 FS-027 D36 90일 삭제 대상이 아니다(공개 표시·중복 거부용)', 'FS-040 D72·D73'),
]
RELATIONS = [dict(source=RV, columns=['user_id'], target='core.app_user', target_columns=['id'],
                  on_delete='RESTRICT', on_update='RESTRICT', note='평가한 회원')]
CODE_LISTS = [
    dict(target=RV, column='module_key', values=MODULES, default=None, note='운영 중인 솔루션(포털 core 제외)'),
    dict(target=RV, column='actor_kind', values=['MEMBER', 'GUEST'], default=None, note='회원 / 게스트'),
]


def apply(d):
    """schema dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if RV in {t['name'] for t in d['tables']}:
        return False
    d['tables'].append(TABLE)
    d['constraints'].extend(CONSTRAINTS)
    d['relations'].extend(RELATIONS)
    d['code_lists'].extend(CODE_LISTS)
    d.update(version='0.15.0', task='FS-040', date='2026-10-01', migration_revision='fs040_app_review')
    d['change_log'].append(dict(version='0.15.0', task='FS-040', date='2026-10-01',
                                change='core.app_review(런처 평가: 별점·한줄평) 1테이블. 공간 FK 없음, 회원 FK만. 스키마 간 FK 0건',
                                status='마이그레이션 fs040_app_review 적용 대상'))
    return True


def main():
    d = json.loads(SCHEMA.read_text(encoding='utf-8'))
    changed = apply(d)
    if changed:
        SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(changed=changed, tables=len(d['tables']), constraints=len(d['constraints']),
                          relations=len(d['relations'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
