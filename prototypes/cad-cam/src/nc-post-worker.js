import { generateNCOutput } from "./nc-post.js";
self.onmessage = async ({ data }) => {
  try {
    self.postMessage({ result: await generateNCOutput(data) });
  } catch (error) {
    self.postMessage({ error: error.message });
  }
};
