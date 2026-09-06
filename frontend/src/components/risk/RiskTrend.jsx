import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
export default function RiskTrend({ data }) {
  return <div style={{ height: 190 }}><ResponsiveContainer><LineChart data={data}><XAxis dataKey="time" /><YAxis domain={[0, 100]} /><Tooltip /><Line type="monotone" dataKey="risk" stroke="#c53030" strokeWidth={3} dot /></LineChart></ResponsiveContainer></div>;
}
