// Loads the committed land mask (public/globe/land-mask.png) into a plain byte array.
import { useEffect, useState } from "react";

export interface LandMask {
  data: Uint8ClampedArray;
  width: number;
  height: number;
}

export function loadLandMask(url: string): Promise<LandMask> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) {
        reject(new Error("no 2D canvas"));
        return;
      }
      ctx.drawImage(image, 0, 0);
      const rgba = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      const data = new Uint8ClampedArray(canvas.width * canvas.height);
      for (let i = 0; i < data.length; i++) data[i] = rgba[i * 4];
      resolve({ data, width: canvas.width, height: canvas.height });
    };
    image.onerror = () => reject(new Error("land mask could not be loaded"));
    image.src = url;
  });
}

let cached: Promise<LandMask> | null = null;

export function useLandMask(): LandMask | null {
  const [mask, setMask] = useState<LandMask | null>(null);
  useEffect(() => {
    let alive = true;
    cached ??= loadLandMask("/globe/land-mask.png");
    cached.then((m) => alive && setMask(m)).catch(() => {
      cached = null;
    });
    return () => {
      alive = false;
    };
  }, []);
  return mask;
}
