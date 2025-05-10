// frontend/src/hooks/useHeatmap.ts
import { useEffect, useState } from 'react';

export interface HeatmapFrame {
  x: number[];
  y: number[];
  z: number[][];
}

export const useHeatmap = () => {
  const [frame, setFrame] = useState<HeatmapFrame | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch('/api/heatmap');

        if (res.ok) setFrame(await res.json());
      } catch (e) {
        // ignore until backend ready
      }
    };
    load();
    const id = setInterval(load, 3000);     // pull every 3 s
    return () => clearInterval(id);
  }, []);
  return frame;
};
