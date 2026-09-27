"""FS-013 §6 R1–R5 + FS-023 R6. Read-only audit; nonzero exit on violations.

R1–R5는 schema.json 메타데이터, R6은 backend 코드의 import를 본다.
"""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUSINESS = {'mes', 'erp', 'fems', 'qms'}
ANCHORS = {'core.workspace', 'core.data_generation'}
FORBIDDEN = {'learning', 'process_map', 'bems'}
SCOPE = ['workspace_id', 'generation_id']


def audit(data):
    errors = []
    for table in data['tables']:
        name = table['name']
        schema = name.split('.')[0]
        if schema in FORBIDDEN:
            errors.append(f'R4: forbidden table {name}')
        if schema in BUSINESS:
            columns = {c['name']: c for c in table['columns']}
            if not all(c in columns and not columns[c]['nullable'] for c in SCOPE):
                errors.append(f'R5: missing/non-required scope key in {name}')
    for relation in data['relations']:
        source, target = relation['source'], relation['target']
        sm, tm = source.split('.')[0], target.split('.')[0]
        if sm in BUSINESS and tm in BUSINESS and sm != tm:
            errors.append(f'R1: {source} -> {target}')
        if sm in BUSINESS and tm == 'core' and target not in ANCHORS:
            errors.append(f'R2: {source} -> {target}')
        if sm == 'core' and tm in BUSINESS:
            errors.append(f'R3: {source} -> {target}')
    return errors


def audit_imports(src=ROOT/'backend/src/fs'):
    """R6: fs/<A>/ 코드가 다른 업무 솔루션 fs/<B>/를 import할 때는 fs.<B>.interface만 허용한다(FS-023 D9·X2)."""
    errors = []
    for owner in sorted(BUSINESS):
        for path in sorted((src/owner).glob('**/*.py')) if (src/owner).is_dir() else []:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    # `from fs.mes import interface`는 이름까지 붙여 fs.mes.interface로 본다.
                    if node.module.count('.') == 1:
                        modules = [f'{node.module}.{a.name}' for a in node.names]
                    else:
                        modules = [node.module]
                else:
                    continue
                for module in modules:
                    parts = module.split('.')
                    if len(parts) >= 2 and parts[0] == 'fs' and parts[1] in BUSINESS - {owner}:
                        if parts[2:3] != ['interface']:
                            errors.append(f'R6: fs/{path.relative_to(src)} imports {module}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, default=ROOT/'docs/db/schema-metadata/schema.json')
    args = parser.parse_args()
    try:
        data = json.loads(args.schema.read_text(encoding='utf-8'))
        errors = audit(data) + audit_imports()
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as exc:
        parser.exit(1, f'ABORT: {exc}\n')
    print(json.dumps({'rules': 'R1–R6', 'tables': len(data['tables']),
                      'foreign_keys': len(data['relations']), 'errors': errors}, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
