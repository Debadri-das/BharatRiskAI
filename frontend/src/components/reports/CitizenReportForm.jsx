import React, { useState } from 'react';
import { submitReport } from '../../services/reportApi';
import { addToQueue } from '../../offline/indexedDB';
import { useEmergencyStore } from '../../store/emergencyStore';

export default function CitizenReportForm({ onSubmitted }){
  const [latitude, setLatitude] = useState('22.546');
  const [longitude, setLongitude] = useState('88.438');
  const [water, setWater] = useState(15);
  const [severity, setSeverity] = useState('MEDIUM');
  const [description, setDescription] = useState('Heavy water accumulation near road edge.');
  const [submitting, setSubmitting] = useState(false);

  async function useGeolocation(){
    if (!navigator.geolocation) return alert('Geolocation not available');
    navigator.geolocation.getCurrentPosition(p => {
      setLatitude(p.coords.latitude.toFixed(4));
      setLongitude(p.coords.longitude.toFixed(4));
    }, () => alert('Unable to get location'));
  }

  async function submit(e){
    e.preventDefault();
    const lat = parseFloat(latitude);
    const lon = parseFloat(longitude);
    if (isNaN(lat) || isNaN(lon)) {
      alert('Please enter valid coordinates');
      return;
    }
    if (!description || description.trim().length < 3) {
      alert('Please enter at least 3 characters of description');
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
    const offlineForced = useEmergencyStore.getState().offlineForced;
    const isOnline = navigator.onLine && !offlineForced;

    try {
      if (isOnline) {
        const res = await submitReport(payload);
        alert(`Citizen Report submitted: Zone ${res.zone_name || res.zone_id} updated`);
        onSubmitted && onSubmitted(res);
      } else {
        await addToQueue({ type: 'report', payload });
        alert('Offline mode: report stored in local IndexedDB queue');
      }
    } catch (err) {
      console.warn('Live submit failed, queueing locally:', err);
      await addToQueue({ type: 'report', payload });
      alert('Network unavailable: report saved to offline queue');
    } finally {
      setSubmitting(false);
    }
  }


  return (
    <form className="card" onSubmit={submit} style={{marginTop:12}}>
      <h4>Citizen Report</h4>
      <div style={{display:'flex',gap:8}}>
        <input placeholder="Latitude" value={latitude} onChange={e=>setLatitude(e.target.value)} />
        <input placeholder="Longitude" value={longitude} onChange={e=>setLongitude(e.target.value)} />
        <button type="button" onClick={useGeolocation}>Use my location</button>
      </div>
      <div style={{marginTop:8}}>
        <label>Water level (cm)</label>
        <input type="number" value={water} onChange={e=>setWater(e.target.value)} />
      </div>
      <div style={{marginTop:8}}>
        <label>Severity</label>
        <select value={severity} onChange={e=>setSeverity(e.target.value)}>
          <option>LOW</option>
          <option>MEDIUM</option>
          <option>HIGH</option>
          <option>CRITICAL</option>
        </select>
      </div>
      <div style={{marginTop:8}}>
        <textarea placeholder="Description" value={description} onChange={e=>setDescription(e.target.value)} rows={3} style={{width:'100%'}} />
      </div>
      <div style={{marginTop:8}}>
        <button className="btn" type="submit" disabled={submitting}>{submitting ? 'Sending...' : 'Submit Report'}</button>
      </div>
    </form>
  )
}
 
