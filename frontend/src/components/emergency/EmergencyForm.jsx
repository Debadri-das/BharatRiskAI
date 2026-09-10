import React, { useState } from 'react';
import { sendEmergency } from '../../services/emergencyApi';
import { addToQueue } from '../../offline/indexedDB';
import { useEmergencyStore } from '../../store/emergencyStore';

export default function EmergencyForm({ onSubmitted }){
  const [latitude, setLatitude] = useState('22.546');
  const [longitude, setLongitude] = useState('88.438');
  const [people, setPeople] = useState(1);
  const [type, setType] = useState('MEDICAL');
  const [notes, setNotes] = useState('');
  const [sending, setSending] = useState(false);

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

    const payload = {
      emergency_type: type.toUpperCase(),
      latitude: lat,
      longitude: lon,
      people: Number(people) || 1,
      description: notes || undefined,
    };
    
    setSending(true);
    const offlineForced = useEmergencyStore.getState().offlineForced;
    const isOnline = navigator.onLine && !offlineForced;

    try {
      if (isOnline) {
        const res = await sendEmergency(payload);
        alert(`Emergency SOS received: ${res.message_id || res.id}`);
        onSubmitted && onSubmitted(res);
      } else {
        await addToQueue({ type: 'emergency', payload });
        alert('Offline mode: emergency SOS queued locally in IndexedDB');
      }
    } catch (err) {
      console.warn('Network send failed, queueing locally:', err);
      await addToQueue({ type: 'emergency', payload });
      alert('Network unavailable: emergency SOS stored in offline queue');
    } finally {
      setSending(false);
    }
  }


  return (
    <form className="card" onSubmit={submit} style={{marginTop:12}}>
      <h4>SOS / Emergency</h4>
      <div style={{display:'flex',gap:8}}>
        <input placeholder="Latitude" value={latitude} onChange={e=>setLatitude(e.target.value)} />
        <input placeholder="Longitude" value={longitude} onChange={e=>setLongitude(e.target.value)} />
        <button type="button" onClick={useGeolocation}>Use my location</button>
      </div>
      <div style={{marginTop:8}}>
        <label>Type</label>
        <select value={type} onChange={e=>setType(e.target.value)}>
          <option value="medical">Medical</option>
          <option value="rescue">Rescue</option>
          <option value="evacuation">Evacuation</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div style={{marginTop:8}}>
        <label>People</label>
        <input type="number" value={people} onChange={e=>setPeople(e.target.value)} />
      </div>
      <div style={{marginTop:8}}>
        <textarea placeholder="Notes" value={notes} onChange={e=>setNotes(e.target.value)} rows={3} style={{width:'100%'}} />
      </div>
      <div style={{marginTop:8}}>
        <button className="btn btn-danger" type="submit" disabled={sending}>{sending ? 'Sending...' : 'Send SOS'}</button>
      </div>
    </form>
  )
}
