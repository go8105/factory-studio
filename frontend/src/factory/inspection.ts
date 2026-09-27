export type Sample = "normal" | "foreign" | "lighting";
export const samples: Record<Sample, string> = {
  normal: "정상",
  foreign: "이물",
  lighting: "조명 변화",
};
export type Recipe = {
  threshold: number;
  minArea: number;
  roi: "full" | "center";
};
export const defaultRecipe: Recipe = {
  threshold: 90,
  minArea: 20,
  roi: "full",
};
export type InspectionRequest = { version: 1; sample: Sample; recipe: Recipe };
export type Region = {
  x: number;
  y: number;
  width: number;
  height: number;
  area: number;
};
export type InspectionResult = {
  version: 1;
  source: "synthetic-browser-v1" | "synthetic-opencv-cpp-v1";
  status: "OK" | "NG";
  regions: Region[];
  falsePixels: number;
  missedPixels: number;
  excludedPixels: number;
};
export const WIDTH = 160,
  HEIGHT = 100;
export function fixture(sample: Sample) {
  const pixels = new Uint8Array(WIDTH * HEIGHT);
  const truth = new Uint8Array(pixels.length);
  for (let y = 0; y < HEIGHT; y++)
    for (let x = 0; x < WIDTH; x++) {
      const i = y * WIDTH + x;
      pixels[i] = sample === "lighting" && x < 40 ? 110 : 210 + ((x + y) % 7);
      if (x >= 75 && x < 77 && y >= 25 && y < 27) pixels[i] = 55;
      if (
        sample !== "normal" &&
        ((x >= 55 && x < 65 && y >= 40 && y < 48) ||
          (x >= 120 && x < 126 && y >= 65 && y < 71))
      ) {
        pixels[i] = 45;
        truth[i] = 1;
      }
    }
  return { pixels, truth };
}
export function roiBox(roi: Recipe["roi"]) {
  return roi === "full"
    ? { x: 0, y: 0, width: WIDTH, height: HEIGHT }
    : { x: 40, y: 20, width: 80, height: 60 };
}
// Adapter boundary: replace this implementation with a remote engine later.
export function inspect(request: InspectionRequest): InspectionResult {
  const { threshold, minArea, roi } = request.recipe;
  if (
    request.version !== 1 ||
    !Object.hasOwn(samples, request.sample) ||
    !["full", "center"].includes(roi) ||
    !Number.isInteger(threshold) ||
    threshold < 0 ||
    threshold > 255 ||
    !Number.isInteger(minArea) ||
    minArea < 1 ||
    minArea > WIDTH * HEIGHT
  )
    throw new Error("Invalid inspection request");
  const { pixels, truth } = fixture(request.sample);
  const box = roiBox(roi);
  const inside = (i: number) =>
    i % WIDTH >= box.x &&
    i % WIDTH < box.x + box.width &&
    Math.floor(i / WIDTH) >= box.y &&
    Math.floor(i / WIDTH) < box.y + box.height;
  const visited = new Uint8Array(pixels.length),
    detected = new Uint8Array(pixels.length);
  const regions: Region[] = [];
  for (let i = 0; i < pixels.length; i++) {
    if (visited[i] || !inside(i) || pixels[i] >= threshold) continue;
    const queue = [i];
    visited[i] = 1;
    let minX = WIDTH,
      maxX = 0,
      minY = HEIGHT,
      maxY = 0;
    for (let head = 0; head < queue.length; head++) {
      const p = queue[head],
        x = p % WIDTH,
        y = Math.floor(p / WIDTH);
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
      const neighbors = [
        y > 0 ? p - WIDTH : -1,
        y < HEIGHT - 1 ? p + WIDTH : -1,
        x > 0 ? p - 1 : -1,
        x < WIDTH - 1 ? p + 1 : -1,
      ];
      for (const n of neighbors)
        if (n >= 0 && !visited[n] && inside(n) && pixels[n] < threshold) {
          visited[n] = 1;
          queue.push(n);
        }
    }
    if (queue.length >= minArea) {
      regions.push({
        x: minX,
        y: minY,
        width: maxX - minX + 1,
        height: maxY - minY + 1,
        area: queue.length,
      });
      for (const p of queue) detected[p] = 1;
    }
  }
  let falsePixels = 0,
    missedPixels = 0,
    excludedPixels = 0;
  for (let i = 0; i < pixels.length; i++) {
    if (!inside(i)) {
      excludedPixels += truth[i];
      continue;
    }
    if (detected[i] && !truth[i]) falsePixels++;
    if (!detected[i] && truth[i]) missedPixels++;
  }
  return {
    version: 1,
    source: "synthetic-browser-v1",
    status: regions.length ? "NG" : "OK",
    regions,
    falsePixels,
    missedPixels,
    excludedPixels,
  };
}
