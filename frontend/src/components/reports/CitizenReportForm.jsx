import React, { useState } from 'react';
import { CheckCircle2, Crosshair, FileText, LoaderCircle, MapPin, Send, TriangleAlert } from 'lucide-react';
import { submitReport } from '../../services/reportApi';

export default function CitizenReportForm({ onSubmitted }){
  const [latitude, setLatitude] = useState('22.546');
  const [longitude, setLongitude] = useState('88.438');
  const [water, setWater] = useState(15);
  const [severity, setSeverity] = useState('MEDIUM');
  const [description, setDescription] = useState('Heavy water accumulation near road edge.');
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  async function useGeolocation(){
    if (!navigator.geolocation) { setFeedback({ type: 'error', message: 'Location is not available in this browser.' }); return; }
    navigator.geolocation.getCurrentPosition(p => {
      setLatitude(p.coords.latitude.toFixed(4));
      setLongitude(p.coords.longitude.toFixed(4));
    }, () => setFeedback({ type: 'error', message: 'Unable to access your location. You can enter coordinates manually.' }));
  }

  async function submit(e){
    e.preventDefault();
    const lat = parseFloat(latitude);
    const lon = parseFloat(longitude);
    if (isNaN(lat) || isNaN(lon)) {
      setFeedback({ type: 'error', message: 'Enter valid latitude and longitude values.' });
      return;
    }
    if (!description || description.trim().length < 3) {
      setFeedback({ type: 'error', message: 'Add at least 3 characters describing the situation.' });
      return;
    }

    const payload = {
      latitude: lat,
      longitude: lon,
      water_level_cm: Number(water) || 0,
      severity,
      description: description.trim(),
    };
    
    setSubmitting(true);
    setFeedback(null);

    try {
      const res = await submitReport(payload);
      setFeedback({ type: 'success', message: `Report saved for ${res.zone_name || `zone ${res.zone_id}`}.` });
      onSubmitted && onSubmitted(res);
    } catch (err) {
      console.warn('Report submission failed:', err);
      setFeedback({ type: 'error', message: err.message?.startsWith('API ') ? `Report was not saved: ${err.message}` : 'Report was not saved. Check that the backend is running at 127.0.0.1:8000.' });
    } finally {
      setSubmitting(false);
    }
  }


  return (
    <form className="field-form panel report-form" onSubmit={submit}>
      <div className="form-heading"><span className="form-icon report"><FileText size={19} /></span><div><span className="section-kicker">GROUND INTELLIGENCE</span><h2>Report local conditions</h2><p>Help response teams see what the sensors cannot.</p></div></div>
      <div className="form-grid two-col"><label className="field-label">Latitude<input inputMode="decimal" value={latitude} onChange={e=>setLatitude(e.target.value)} /></label><label className="field-label">Longitude<input inputMode="decimal" value={longitude} onChange={e=>setLongitude(e.target.value)} /></label></div>
      <button className="location-button" type="button" onClick={useGeolocation}><Crosshair size={15} /> Use my current location</button>
      <div className="form-grid two-col"><label className="field-label">Water level <span>(cm)</span><input type="number" min="0" value={water} onChange={e=>setWater(e.target.value)} /></label><label className="field-label">Severity<select value={severity} onChange={e=>setSeverity(e.target.value)}>
          <option>LOW</option>
          <option>MEDIUM</option>
          <option>HIGH</option>
          <option>CRITICAL</option>
        </select></label></div>
      <label className="field-label">What are you seeing?<textarea placeholder="Describe water depth, blocked roads, or damage..." value={description} onChange={e=>setDescription(e.target.value)} rows={4} /></label>
      {feedback && <div className={`form-feedback ${feedback.type}`}>{feedback.type === 'success' ? <CheckCircle2 size={16} /> : <TriangleAlert size={16} />}{feedback.message}</div>}
      <button className="btn form-submit" type="submit" disabled={submitting}>{submitting ? <><LoaderCircle className="spin" size={16} /> Sending report</> : <><Send size={16} /> Submit report</>}</button>
    </form>
  )
}
 
