"""FS-013 §6 R1–R5. Read-only metadata audit; nonzero exit on violations."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUSINESS = {'mes', 'erp', 'fems'}
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, default=ROOT/'docs/db/schema-metadata/schema.json')
    args = parser.parse_args()
    try:
        data = json.loads(args.schema.read_text(encoding='utf-8'))
        errors = audit(data)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'ABORT: {exc}\n')
    print(json.dumps({'rules': 'R1–R5', 'tables': len(data['tables']),
                      'foreign_keys': len(data['relations']), 'errors': errors}, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
