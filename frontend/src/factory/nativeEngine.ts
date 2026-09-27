import { api, ApiError } from "../shared/api";
import type { Engine } from "./inspectionRun";
import type { InspectionResult } from "./inspection";
export class NativeEngine {
  private requests = new Set<AbortController>();
  constructor(
    public csrf: string | undefined,
    public fail: (error: unknown) => void,
  ) {}
  cancel = () => {
    this.requests.forEach((c) => c.abort());
    this.requests.clear();
  };
  execute: Engine = async (request, requestId = crypto.randomUUID()) => {
    const controller = new AbortController();
    this.requests.add(controller);
    const timeout = setTimeout(() => controller.abort(), 3000);
    try {
      const { data } = await api<{
        requestId: string;
        result: InspectionResult;
        inspectionMs: number;
      }>("/api/v1/factory/vision/inspect", {
        method: "POST",
        body: { requestId, request },
        csrf: this.csrf,
        signal: controller.signal,
      });
      if (controller.signal.aborted)
        throw new Error("C++ 검사 요청이 취소되었습니다.");
      if (
        data.requestId !== requestId ||
        data.result?.source !== "synthetic-opencv-cpp-v1" ||
        !Number.isFinite(data.inspectionMs) ||
        data.inspectionMs < 0 ||
        !Array.isArray(data.result.regions) ||
        !["OK", "NG"].includes(data.result.status)
      )
        throw new Error("C++ 검사 응답 형식이 올바르지 않습니다.");
      return { result: data.result, inspectionMs: data.inspectionMs };
    } catch (error) {
      if (error instanceof ApiError && [401, 410].includes(error.status))
        this.fail(error);
      if (controller.signal.aborted)
        throw new Error(
          "C++ 검사 요청이 취소되었거나 응답 제한 시간을 초과했습니다.",
          { cause: error },
        );
      throw error;
    } finally {
      clearTimeout(timeout);
      this.requests.delete(controller);
    }
  };
}
