# POC-01 · 일반 FDM 비누 마찰판 시험편

2026-10-05 / codex/soap-cad-review. 사용자 답변: 출력 장비 미정, 일반 FDM 기준.

## 의도와 범위
지원서 5~6쪽의 플라스틱 마찰 원리 검증을 첫 단계로 해석했다. PDF는 참고자료다.
3D CAD는 설계, FDM은 제작, 슬라이서는 적층 경로 생성이다. CAD와 3D 프린팅은 대안 관계가 아니다.
이번 CAD-01 CNC CAM 재생은 출력 공정과 별개다. 완성 회전 기구·금형은 미착수.

## 결과
- `prototypes/cad-cam/soap-poc.html`: STL 기반 회전/확대·판 교체·분해·시험 비누 표시·다운로드.
- `tools/build-soap-poc.mjs`: Manifold3.5.4 boolean 생성기. mm, 트레이84×64×14, 판78.4×58.4×3, 돌기0.6/1.0/1.4, 편측 여유0.4.
- `public/soap-poc/`: STL4개·형상보고·출력 안내·측정 CSV·전체 ZIP. 원본 PDF/개인정보 미포함.
- 화면은 조립 검토용. 치수 변경은 소스에서 재생성. 웹 자유 파라미터 편집·분쇄 물리는 추가하지 않았다.
- 시험재료 PETG 후보, PLA 끼움 확인 후보. 최종 재질/사출은 시험 후 결정. PETG 추천 근거는 일반 기계부품 용도이지 비누 내마모 인증이 아니다.
- 근거: [Prusa PETG](https://help.prusa3d.com/article/petg_2059), [PLA](https://help.prusa3d.com/article/pla_2062).

## 검증
- 생성기 실행: 4부품 모두 NoError·단일 연결체·양의 체적. 조립 교차체적 수치오차 범위0.
- npm test: 기존9 + STL4 = 13 통과. 내보낸 바이너리 삼각형 연결/방향/양의 체적 검사.
- npm run build 성공(공통 Three 청크569KB 경고), format:check 통과.
- 실제 브라우저 B→C→B 교체, 분해28mm, 시험 비누 체크, 390px 가로 넘침 없음, 오류로그0.
- ZIP 실제 다운로드 완료. 화면 `assets/soap-poc-01.png`.
- 미실행: 실제 프린터/슬라이서, 절삭력·마모·분말·재료 안전·방수·공차 시험, Safari/실기기, DB 검사. DB 변경 없음.

## 제약과 다음 작업
얇은 돌기/인접 슬롯의 FDM 재현성은 층별 경로 확인이 필요하다. 작은 비누20×18×8로 중앙 시험한다.
돌기A는 림보다 낮으므로 큰 비누 호환성을 주장하지 않는다. 실험 분말은 사용용이 아니다.
사용자 확인 후 출력 업체/장비 프로파일 적용과 실제 A/B/C 시험. 결과 없이는 회전 본체·최종 재료 성능을 확정하지 않는다.
ROADMAP-02 유지. 운영 제품/DB 변경·push·배포 없음.

재현: `cd prototypes/cad-cam && npm ci && npm run poc:build && npm test && npm run build`.
ZIP: `python3 tools/package-soap-poc.py`. 웹: `npm run dev`, localhost5241/soap-poc.html.
