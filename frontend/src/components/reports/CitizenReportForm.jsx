import React, { useState } from 'react';
import api from '../../services/api';
import { addToQueue } from '../../offline/indexedDB';

export default function CitizenReportForm({ onSubmitted }){
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [water, setWater] = useState(10);
  const [severity, setSeverity] = useState('MEDIUM');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function useGeolocation(){
    if (!navigator.geolocation) return alert('Geolocation not available');
    navigator.geolocation.getCurrentPosition(p => {
      setLatitude(p.coords.latitude);
      setLongitude(p.coords.longitude);
    }, () => alert('Unable to get location'));
  }

  async function submit(e){
    e.preventDefault();
    const payload = { latitude: parseFloat(latitude), longitude: parseFloat(longitude), water_level_cm: Number(water), severity, description };
    setSubmitting(true);
    try{
      if (navigator.onLine){
        const res = await api.postReport(payload);
        alert('Report submitted: ' + JSON.stringify(res));
        onSubmitted && onSubmitted(res);
      } else {
        await addToQueue({type:'report', payload});
        alert('Offline: report queued locally');
      }
    }catch(err){
      console.error(err);
      alert('Failed to submit report: ' + err?.message);
    }finally{setSubmitting(false)}
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
 
