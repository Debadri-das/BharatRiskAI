export default function ReportDetails({ report }) { return report ? <div className="panel" style={{ padding: 16 }}>{report.description}</div> : null; }
