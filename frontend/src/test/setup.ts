import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup, configure } from "@testing-library/react";
// 기본 1초는 lazy 라우트 묶음을 기다리기에 빠듯하다 — 파일이 늘어 병렬 부하가 커지면 먼저 터진다.
// 찾으면 바로 끝나므로 통과하는 테스트는 느려지지 않는다.
configure({ asyncUtilTimeout: 5000 });
afterEach(cleanup);
