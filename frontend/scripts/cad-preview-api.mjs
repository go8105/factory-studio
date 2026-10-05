// Local, synthetic API fixture for UI verification. No database or real login.
import http from "node:http";
const session = {
  actorKind: "GUEST",
  workspaceId: 901,
  generationId: 1,
  roles: ["GUEST"],
  csrfToken: "synthetic-preview",
  expiresAt: null,
};
http
  .createServer((req, res) => {
    res.setHeader("Content-Type", "application/json");
    const reply = (data, status = 200) => {
      res.statusCode = status;
      res.end(
        JSON.stringify(
          status === 200
            ? { data }
            : {
                error: { code: "SESSION_REQUIRED", message: "모의 세션 없음" },
              },
        ),
      );
    };
    const path = req.url;
    if (path === "/api/v1/core/guest-sessions" && req.method === "POST") {
      res.setHeader(
        "Set-Cookie",
        "cad_preview=1; HttpOnly; SameSite=Lax; Path=/",
      );
      return reply(session);
    }
    if (path === "/api/v1/core/sessions/current") {
      if (req.method === "DELETE") {
        res.setHeader("Set-Cookie", "cad_preview=; Max-Age=0; Path=/");
        return reply(null);
      }
      return req.headers.cookie?.includes("cad_preview=1")
        ? reply(session)
        : reply(null, 401);
    }
    if (path === "/api/v1/core/workspace/modules")
      return reply(
        ["mes", "erp", "fems", "qms", "wms", "bems", "spc", "gw"].map(
          (moduleKey) => ({ moduleKey, enabled: true, updatedAt: null }),
        ),
      );
    if (path === "/api/v1/core/reviews/summary") return reply([]);
    reply(null, 404);
  })
  .listen(8042, "127.0.0.1", () =>
    console.log("Synthetic CAD preview API on 127.0.0.1:8042 (no database)"),
  );
