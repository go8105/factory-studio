import { analyzeStock } from "./nc-stock.js";
self.onmessage = ({ data }) => {
  try {
    self.postMessage({
      revision: data.revision,
      analysis: analyzeStock(data.nc, data.reference, data.setup),
    });
  } catch (error) {
    self.postMessage({ revision: data.revision, error: error.message });
  }
};
