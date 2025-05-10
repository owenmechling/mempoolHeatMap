import Plot from 'react-plotly.js';
import { useHeatmap } from './hooks/useHeatmap';

function App() {
  const frame = useHeatmap();

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-4">Live Mempool Heat‑Map</h1>

      {frame ? (
        <Plot
          data={[
            {
              x: frame.x.map((b) => `${b} sat/vB`),
              y: frame.y.map((i) => `${i*50} kB`),   // if each row = 50 kB
              z: frame.z,
              type: 'heatmap',
              colorscale: 'Jet',            // more gradienty look
              zsmooth: 'best',              // slight interpolation
              hovertemplate:
                'Fee‑rate %{x}<br>~%{y} chunk<br>%{z:.0f} vbytes<extra></extra>',
            },
          ]}
          layout={{
            width: 800,
            height: 500,
            yaxis: { autorange: 'reversed' }, // small txs at top
            margin: { t: 30 },
          }}
          config={{ displayModeBar: false }}
        />
      ) : (
        <p className="italic">Waiting for first frame…</p>
      )}
    </div>
  );
}

export default App;
