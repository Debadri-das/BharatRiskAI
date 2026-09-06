import React from "react";
import { createRoot } from "react-dom/client";
import 'leaflet/dist/leaflet.css';
import App from "./App";
import "./index.css";

try{
  console.log('BharatRisk UI starting');
  const root = document.getElementById('root');
  if(!root) throw new Error('No root element');
  createRoot(root).render(<App />);
}catch(err){
  console.error('Render error', err);
  const root = document.getElementById('root');
  if(root) root.innerText = 'App error: ' + (err.message || String(err));
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js').catch(() => {});
}
