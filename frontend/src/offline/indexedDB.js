// Minimal IndexedDB wrapper for queued reports/emergencies
const DB_NAME = 'bharatrisk_offline_v1';
const STORE = 'queue';

function openDB(){
  return new Promise((res, rej)=>{
    const r = indexedDB.open(DB_NAME,1);
    r.onupgradeneeded = () => {
      const db = r.result;
      if(!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  })
}

export async function addToQueue(payload){
  const db = await openDB();
  return new Promise((res, rej)=>{
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).add({payload, status:'PENDING', created_at:Date.now()});
    tx.oncomplete = ()=>res(true);
    tx.onerror = ()=>rej(tx.error);
  })
}

export async function listQueue(){
  const db = await openDB();
  return new Promise((res, rej)=>{
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = ()=>res(req.result || []);
    req.onerror = ()=>rej(req.error);
  })
}

export async function clearItem(id){
  const db = await openDB();
  return new Promise((res, rej)=>{
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = ()=>res(true);
    tx.onerror = ()=>rej(tx.error);
  })
}
export async function putQueued(item) {
  const db = await openDB();
  return new Promise((res, rej) => {
    const tx = db.transaction(STORE, 'readwrite');
    try{
      const store = tx.objectStore(STORE);
      const id = item.id || (crypto && crypto.randomUUID ? crypto.randomUUID() : Date.now());
      store.put({ ...item, id, createdAt: new Date().toISOString() });
    }catch(e){ tx.abort(); return rej(e); }
    tx.oncomplete = () => res(true);
    tx.onerror = () => rej(tx.error);
  })
}

export async function allQueued(){
  const db = await openDB();
  return new Promise((res, rej)=>{
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = ()=>res(req.result || []);
    req.onerror = ()=>rej(req.error);
  })
}
