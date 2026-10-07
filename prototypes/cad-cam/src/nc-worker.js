import { parseNC } from "./nc-parser.js";
self.onmessage = async ({ data }) => {
  const { revision, text, settings } = data;
  try {
    const result = parseNC(text, settings, (progress) =>
      self.postMessage({ revision, progress }),
    );
    const digest = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(text),
    );
    result.sourceHash = Array.from(new Uint8Array(digest), (v) =>
      v.toString(16).padStart(2, "0"),
    ).join("");
    self.postMessage({ revision, result });
  } catch (error) {
    self.postMessage({ revision, error: error.message });
  }
};
