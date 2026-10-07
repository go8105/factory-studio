import { analyzeEnergy } from "./nc-energy.js";
self.onmessage = ({ data }) => {
  try {
    self.postMessage({
      revision: data.revision,
      analysis: analyzeEnergy(data.nc, data.stock, data.model),
    });
  } catch (error) {
    self.postMessage({ revision: data.revision, error: error.message });
  }
};
