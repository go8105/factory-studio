export type ErrorEnvelope = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    public error: ErrorEnvelope,
  ) {
    super(error.message);
  }
}
export type Session = {
  actorKind: "GUEST" | "MEMBER";
  workspaceId: number;
  generationId: number;
  roles: string[];
  expiresAt: string | null;
  csrfToken: string;
};
export type Module = {
  moduleKey: string;
  enabled: boolean;
  updatedAt: string | null;
};
export type Workspace = {
  id: number;
  workspaceKind: string;
  configVersion: number;
  expiresAt: string | null;
  createdAt: string;
};
export type Envelope<T> = {
  data: T;
  page?: { offset: number; limit: number; total: number };
};
export async function api<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    csrf?: string;
    key?: string;
    signal?: AbortSignal;
  } = {},
): Promise<Envelope<T>> {
  let response: Response;
  try {
    // "/api/"로 시작하면 솔루션 경로 그대로, 아니면 포털(core) 경로다.
    response = await fetch(
      path.startsWith("/api/") ? path : `/api/v1/core${path}`,
      {
        method: options.method ?? "GET",
        credentials: "same-origin",
        signal: options.signal,
        headers: {
          ...(options.body !== undefined
            ? { "Content-Type": "application/json" }
            : {}),
          ...(options.csrf ? { "X-CSRF-Token": options.csrf } : {}),
          ...(options.key ? { "Idempotency-Key": options.key } : {}),
        },
        body:
          options.body !== undefined ? JSON.stringify(options.body) : undefined,
      },
    );
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(0, {
      code: "NETWORK_UNCERTAIN",
      message: "응답을 확인하지 못했습니다. 같은 요청으로 다시 확인해 주세요.",
    });
  }
  if (response.status === 204) return { data: undefined as T };
  const payload = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      response.status,
      payload?.error ?? {
        code: "HTTP_ERROR",
        message: "요청을 처리하지 못했습니다.",
      },
    );
  if (!payload || !("data" in payload))
    throw new ApiError(0, {
      code: "NETWORK_UNCERTAIN",
      message: "응답을 확인하지 못했습니다. 같은 요청으로 다시 확인해 주세요.",
    });
  return payload;
}
// 응답 불확실 시 같은 동작·본문은 같은 키로 재시도한다. 토큰·비밀번호는 영속 저장하지 않는다.
export class MutationKeys {
  private keys = new Map<string, string>();
  get(operation: string) {
    let key = this.keys.get(operation);
    if (!key) {
      key = crypto.randomUUID();
      this.keys.set(operation, key);
    }
    return key;
  }
  complete(operation: string) {
    this.keys.delete(operation);
  }
}
