import React, { useState } from 'react';
import { AlertOctagon, CheckCircle2, Crosshair, LoaderCircle, MapPin, Send, TriangleAlert } from 'lucide-react';
import { sendEmergency } from '../../services/emergencyApi';

export default function EmergencyForm({ onSubmitted }){
  const [latitude, setLatitude] = useState('22.546');
  const [longitude, setLongitude] = useState('88.438');
  const [people, setPeople] = useState(1);
  const [type, setType] = useState('MEDICAL');
  const [notes, setNotes] = useState('');
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState(null);

  async function useGeolocation(){
    if (!navigator.geolocation) { setFeedback({ type: 'error', message: 'Location is not available in this browser.' }); return; }
    navigator.geolocation.getCurrentPosition(p => {
      setLatitude(p.coords.latitude.toFixed(4));
      setLongitude(p.coords.longitude.toFixed(4));
    }, () => setFeedback({ type: 'error', message: 'Unable to access your location. Enter coordinates manually.' }));
  }

  async function submit(e){
    e.preventDefault();
    const lat = parseFloat(latitude);
    const lon = parseFloat(longitude);
    if (isNaN(lat) || isNaN(lon)) {
      setFeedback({ type: 'error', message: 'Enter valid latitude and longitude values.' });
      return;
    }

    const payload = {
      emergency_type: type.toUpperCase(),
      latitude: lat,
      longitude: lon,
      people: Number(people) || 1,
      description: notes || undefined,
    };
    
    setSending(true);
    setFeedback(null);

    try {
      const res = await sendEmergency(payload);
      setFeedback({ type: 'success', message: `SOS saved. Reference ${res.message_id || res.id}.` });
      onSubmitted && onSubmitted(res);
    } catch (err) {
      console.warn('SOS submission failed:', err);
      setFeedback({ type: 'error', message: err.message?.startsWith('API ') ? `SOS was not saved: ${err.message}` : 'SOS was not saved. Check that the backend is running at 127.0.0.1:8000.' });
    } finally {
      setSending(false);
    }
  }


  return (
    <form className="field-form panel sos-form" onSubmit={submit}>
      <div className="form-heading"><span className="form-icon sos"><AlertOctagon size={19} /></span><div><span className="section-kicker">EMERGENCY CHANNEL</span><h2>Request immediate help</h2><p>Your SOS is routed to the response queue with your location.</p></div></div>
      <div className="sos-callout"><MapPin size={16} /><span><strong>Location attached</strong><small>Confirm the coordinates before sending.</small></span></div>
      <div className="form-grid two-col"><label className="field-label">Latitude<input inputMode="decimal" value={latitude} onChange={e=>setLatitude(e.target.value)} /></label><label className="field-label">Longitude<input inputMode="decimal" value={longitude} onChange={e=>setLongitude(e.target.value)} /></label></div>
      <button className="location-button" type="button" onClick={useGeolocation}><Crosshair size={15} /> Refresh my location</button>
      <div className="form-grid two-col"><label className="field-label">Emergency type<select value={type} onChange={e=>setType(e.target.value)}>
          <option value="medical">Medical</option>
          <option value="rescue">Rescue</option>
          <option value="evacuation">Evacuation</option>
          <option value="other">Other</option>
        </select></label><label className="field-label">People affected<input type="number" min="1" value={people} onChange={e=>setPeople(e.target.value)} /></label></div>
      <label className="field-label">Additional details<textarea placeholder="What help is needed right now?" value={notes} onChange={e=>setNotes(e.target.value)} rows={4} /></label>
      {feedback && <div className={`form-feedback ${feedback.type}`}>{feedback.type === 'success' ? <CheckCircle2 size={16} /> : <TriangleAlert size={16} />}{feedback.message}</div>}
      <button className="btn sos-submit" type="submit" disabled={sending}>{sending ? <><LoaderCircle className="spin" size={16} /> Sending SOS</> : <><Send size={16} /> Send SOS</>}</button>
    </form>
  )
}
