"""운영자 초기 구성. 합성 예제 회사만 만드는 명시적 도구에서 호출."""

from sqlalchemy import text

from fs.common.clock import real_today
from fs.core.service import create_member_account


def create_example_company(c, admin_password, staff_password):
    if c.execute(
        text(
            "SELECT 1 FROM core.app_user WHERE login_id IN ('hugh-admin','hugh-staff')"
        )
    ).first():
        raise ValueError(
            "예제 아이디가 이미 있습니다. 기존 계정/비밀번호를 덮어쓰지 않습니다."
        )
    users = [
        create_member_account(
            c, "hugh-admin", "hugh-D 관리자", admin_password, real_today()
        ),
        create_member_account(
            c, "hugh-staff", "hugh-D 직원", staff_password, real_today()
        ),
    ]
    w = c.execute(
        text(
            "INSERT INTO core.workspace(workspace_kind) VALUES ('COMPANY') RETURNING id"
        )
    ).scalar_one()
    g = c.execute(
        text(
            "INSERT INTO core.data_generation(workspace_id,seed_version,seed_date,status,activated_at) VALUES (:w,'company-example-1',:day,'active',now()) RETURNING id"
        ),
        {"w": w, "day": real_today()},
    ).scalar_one()
    c.execute(
        text("UPDATE core.workspace SET active_generation_id=:g WHERE id=:w"),
        {"w": w, "g": g},
    )
    c.execute(
        text(
            "INSERT INTO core.company(workspace_id,name,is_example) VALUES (:w,'hugh-D Company',true)"
        ),
        {"w": w},
    )
    c.execute(
        text(
            "INSERT INTO core.workspace_module(workspace_id,module_key,enabled,seeded_generation_id) VALUES (:w,'hr',true,:g)"
        ),
        {"w": w, "g": g},
    )
    c.execute(
        text(
            "INSERT INTO core.workspace_module(workspace_id,module_key,enabled,seeded_generation_id) VALUES (:w,'gw',true,:g)"
        ),
        {"w": w, "g": g},
    )
    params = {"w": w, "g": g}
    department = c.execute(
        text(
            "INSERT INTO hr.department(workspace_id,generation_id,code,name) VALUES (:w,:g,'HUGH','hugh-D Company') RETURNING id"
        ),
        params,
    ).scalar_one()
    grade = c.execute(
        text(
            "INSERT INTO hr.title(workspace_id,generation_id,title_kind,code,name,rank_order) VALUES (:w,:g,'GRADE','STAFF','구성원',1) RETURNING id"
        ),
        params,
    ).scalar_one()
    pattern = c.execute(
        text(
            "INSERT INTO hr.work_pattern(workspace_id,generation_id,code,name,pattern_kind,start_time,scheduled_minutes,break_minutes) VALUES (:w,:g,'DAY','예제 주간근무','DAY','09:00',480,60) RETURNING id"
        ),
        params,
    ).scalar_one()
    c.execute(
        text("INSERT INTO hr.work_policy(workspace_id,generation_id) VALUES (:w,:g)"),
        params,
    )
    for i, u in enumerate(users):
        employee = c.execute(
            text("""INSERT INTO hr.employee(workspace_id,generation_id,employee_code,name,hire_date,department_id,grade_id,work_pattern_id)
          VALUES (:w,:g,:code,:name,:day,:department,:grade,:pattern) RETURNING id"""),
            {
                **params,
                "code": f"HUGH-{i + 1:03}",
                "name": "예제 관리자" if i == 0 else "예제 직원",
                "day": real_today(),
                "department": department,
                "grade": grade,
                "pattern": pattern,
            },
        ).scalar_one()
        c.execute(
            text(
                "INSERT INTO core.company_member(workspace_id,user_id,role) VALUES (:w,:u,:role)"
            ),
            {"w": w, "u": u["userId"], "role": "OWNER" if i == 0 else "MEMBER"},
        )
        c.execute(
            text(
                "INSERT INTO hr.work_account(workspace_id,generation_id,user_id,employee_id,work_role) VALUES (:w,:g,:u,:e,:role)"
            ),
            {
                **params,
                "u": u["userId"],
                "e": employee,
                "role": "ADMIN" if i == 0 else "STAFF",
            },
        )
        c.execute(
            text(
                "INSERT INTO hr.leave_balance(workspace_id,generation_id,employee_id,leave_year,granted_days) VALUES (:w,:g,:e,:year,15)"
            ),
            {**params, "e": employee, "year": str(real_today().year)},
        )
    return {
        "companyId": w,
        "company": "hugh-D Company",
        "adminLogin": "hugh-admin",
        "staffLogin": "hugh-staff",
    }


def prepare_example_company(c):
    """계정은 비밀번호 입력 전 로그인 불가. 임시 난수는 저장/출력하지 않는다."""
    import secrets

    result = create_example_company(
        c, secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    )
    c.execute(
        text(
            "UPDATE core.app_user SET status='disabled',disabled_at=now() WHERE login_id IN ('hugh-admin','hugh-staff')"
        )
    )
    return result


def activate_example_company(c, admin_password, staff_password):
    from fs.common.security import hash_password

    rows = (
        c.execute(
            text("""SELECT u.id,u.login_id,u.status,c.workspace_id,a.work_role
      FROM core.app_user u JOIN core.company_member m ON m.user_id=u.id
      JOIN core.company c ON c.workspace_id=m.workspace_id
      JOIN core.workspace w ON w.id=c.workspace_id
      JOIN hr.work_account a ON a.workspace_id=w.id AND a.generation_id=w.active_generation_id AND a.user_id=u.id
      WHERE u.login_id IN ('hugh-admin','hugh-staff') AND c.name='hugh-D Company' AND c.is_example
      FOR UPDATE OF u""")
        )
        .mappings()
        .all()
    )
    if (
        len(rows) != 2
        or len({r["workspace_id"] for r in rows}) != 1
        or any(r["status"] != "disabled" for r in rows)
    ):
        raise ValueError(
            "초기 비밀번호 설정 대기 중인 예제 회사의 두 계정만 활성화할 수 있습니다."
        )
    for login, password, role in [
        ("hugh-admin", admin_password, "ADMIN"),
        ("hugh-staff", staff_password, "STAFF"),
    ]:
        row = next(
            (r for r in rows if r["login_id"] == login and r["work_role"] == role), None
        )
        if row is None or len(password) < 10:
            raise ValueError("계정 연결 또는 비밀번호 기준을 확인하세요.")
        c.execute(
            text(
                "UPDATE core.app_user SET password_hash=:hash,status='active',disabled_at=NULL WHERE id=:id"
            ),
            {"hash": hash_password(password), "id": row["id"]},
        )
    return {"company": "hugh-D Company", "companyId": rows[0]["workspace_id"]}
