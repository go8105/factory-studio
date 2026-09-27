#!/bin/sh
# 운영 서버(Ubuntu 24.04 x86_64)용 inspection_core를 맥 Docker에서 빌드한다(FS-VISION 배포).
# 서버(1 vCPU·2GB)에서 OpenCV를 컴파일하지 않으려고 만든 경로다. 결과: work/inspection-core-linux/bin/inspection_core
# OpenCV·JSON은 CMake가 고정 버전·SHA-256으로 받아 정적으로 넣는다(INSPECTION_FETCH_DEPS). 웹 비교 테스트용 Node 24도 컨테이너 안에서 받는다.
set -eu
cd "$(dirname "$0")/../.."
docker run --rm --platform linux/amd64 -e JOBS="${JOBS:-1}" -v "$PWD":/src -w /src ubuntu:24.04 sh -eu -c '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq cmake g++ make ca-certificates curl xz-utils >/dev/null
  curl -fsSL https://nodejs.org/dist/v24.11.1/node-v24.11.1-linux-x64.tar.xz | tar -xJ -C /opt
  export PATH=/opt/node-v24.11.1-linux-x64/bin:$PATH
  cmake -S native/inspection_core -B work/inspection-core-linux -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build work/inspection-core-linux --parallel "${JOBS:-1}" >/dev/null
  # 웹 비교(19,968건)는 에뮬레이션에서 ctest 제한(120초)을 넘으므로 제한 없이 직접 돌린다.
  ctest --test-dir work/inspection-core-linux --output-on-failure -E web_native_parity
  node native/inspection_core/tests/parity.mjs work/inspection-core-linux/bin/inspection_core
  work/inspection-core-linux/bin/inspection_core --timed < native/inspection_core/examples/foreign.json
  echo
  ldd work/inspection-core-linux/bin/inspection_core
'
