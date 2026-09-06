import React, { useState } from 'react';
import api from '../../services/api';
import { addToQueue } from '../../offline/indexedDB';

export default function EmergencyForm({ onSubmitted }){
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [people, setPeople] = useState(1);
  const [type, setType] = useState('medical');
  const [notes, setNotes] = useState('');
  const [sending, setSending] = useState(false);

  async function useGeolocation(){
    if (!navigator.geolocation) return alert('Geolocation not available');
    navigator.geolocation.getCurrentPosition(p => {
      setLatitude(p.coords.latitude);
      setLongitude(p.coords.longitude);
    }, () => alert('Unable to get location'));
  }

  async function submit(e){
    e.preventDefault();
    const payload = { emergency_type: type, latitude: parseFloat(latitude), longitude: parseFloat(longitude), people: Number(people), description: notes };
    setSending(true);
    try{
      if (navigator.onLine){
        const res = await api.postEmergency(payload);
        alert('Emergency sent: ' + JSON.stringify(res));
        onSubmitted && onSubmitted(res);
      } else {
        await addToQueue({type:'emergency', payload});
        alert('Offline: emergency queued locally');
      }
    }catch(err){
      console.error(err);
      alert('Failed to send emergency: ' + err?.message);
    }finally{setSending(false)}
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
