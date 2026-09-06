export default function ParameterSlider({ label, value, min, max, step = 1, onChange, suffix = '' }) {
  return <label style={{ display: 'grid', gap: 6 }}><span style={{ display: 'flex', justifyContent: 'space-between' }}>{label}<b>{value}{suffix}</b></span><input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} /></label>;
}
