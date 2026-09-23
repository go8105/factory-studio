"""문서 이동 후 마크다운 상대 링크를 일괄 보정한다.

파일명을 기준으로 현재 실제 위치를 찾아, 링크가 걸린 문서에서 본 문서 기준의
올바른 상대 경로로 다시 계산한다. 링크 텍스트는 건드리지 않는다.

재실행 가능하다. 이미 올바른 링크는 바꾸지 않는다.
실행: python3 tools/fix_doc_links.py           (변경 내용만 출력, 파일 수정 안 함)
      python3 tools/fix_doc_links.py --write   (실제 수정)
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
WRITE = '--write' in sys.argv

# 문서 폴더 안의 마크다운 파일명 → 실제 경로. 같은 이름이 둘이면 보정 대상에서 뺀다.
index, dup = {}, set()
for p in DOCS.rglob('*.md'):
    if p.name in index:
        dup.add(p.name)
    index[p.name] = p
for n in dup:
    index.pop(n, None)

LINK = re.compile(r'\]\(([^)]+)\)')
changes, unresolved = [], []

for doc in sorted(DOCS.rglob('*.md')):
    text = doc.read_text()

    def repl(m):
        href = m.group(1)
        # 외부 링크, 앵커, 절대 경로는 건드리지 않는다.
        if href.startswith(('http://', 'https://', '#', '/')):
            return m.group(0)
        path, _, frag = href.partition('#')
        name = os.path.basename(path)
        if not name.endswith('.md'):
            return m.group(0)
        # 이미 올바르게 가리키고 있으면 그대로 둔다.
        if (doc.parent / path).resolve().exists():
            return m.group(0)
        target = index.get(name)
        if target is None:
            unresolved.append((str(doc.relative_to(ROOT)), href))
            return m.group(0)
        rel = os.path.relpath(target, doc.parent)
        new = rel + ('#' + frag if frag else '')
        changes.append((str(doc.relative_to(ROOT)), href, new))
        return '](' + new + ')'

    fixed = LINK.sub(repl, text)
    if WRITE and fixed != text:
        doc.write_text(fixed)

print(f'{"수정" if WRITE else "미리보기"} — 링크 {len(changes)}건')
for f, old, new in changes:
    print(f'  {f}\n      {old}  →  {new}')
if dup:
    print(f'\n동일 파일명이 여러 곳에 있어 자동 보정에서 제외: {sorted(dup)}')
if unresolved:
    print(f'\n대상 문서를 찾지 못한 링크 {len(unresolved)}건 (수동 확인 필요)')
    for f, href in unresolved:
        print(f'  {f}  →  {href}')
if not WRITE:
    print('\n실제로 반영하려면: python3 tools/fix_doc_links.py --write')
