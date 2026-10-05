import { createStockGrid, sweep, residualVolume } from "./model.js";
let state;
self.onmessage = ({ data }) => {
  try {
    const { model, path, fraction, revision, request } = data;
    const time = path.seconds * fraction;
    if (!state || state.revision !== revision || time < state.time)
      state = {
        revision,
        grid: createStockGrid(model),
        index: 1,
        pos: path.points[0],
        time: 0,
      };
    while (state.index < path.points.length) {
      const a = path.points[state.index - 1],
        b = path.points[state.index];
      if (a.time > time) break;
      const t =
        b.time === a.time
          ? 1
          : Math.min(1, (time - a.time) / (b.time - a.time));
      const end = {
        ...b,
        x: a.x + (b.x - a.x) * t,
        y: a.y + (b.y - a.y) * t,
        z: a.z + (b.z - a.z) * t,
      };
      sweep(state.grid, state.pos, end, path.tool.diameter / 2);
      state.pos = end;
      if (t < 1) break;
      state.index++;
    }
    state.time = time;
    const grid = {
      ...state.grid,
      heights: state.grid.heights.slice(),
      initial: undefined,
    };
    self.postMessage(
      {
        grid,
        pos: state.pos,
        revision,
        request,
        fraction,
        residual: residualVolume(model, state.grid),
      },
      [grid.heights.buffer],
    );
  } catch (error) {
    self.postMessage({
      error: error.message,
      revision: data.revision,
      request: data.request,
    });
  }
};
