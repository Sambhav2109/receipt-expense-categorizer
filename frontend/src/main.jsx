import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const categories = ['All','Groceries','Food','Transport','Travel','Shopping','Personal Care','Office','Utilities','Healthcare','Other'];
const formatCurrency = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'}).format(value || 0);
function App() {
  const [items,setItems]=useState([]), [meta,setMeta]=useState({total:0,count:0}), [category,setCategory]=useState('All'), [search,setSearch]=useState(''), [start,setStart]=useState(''), [end,setEnd]=useState(''), [selected,setSelected]=useState(null), [busy,setBusy]=useState(false), [error,setError]=useState('');
  const load=()=>fetch(`${API}/receipts?${new URLSearchParams({...(category!=='All'?{category}:{}),...(search?{search}:{}),...(start?{start_date:start}:{}),...(end?{end_date:end}:{})})}`).then(r=>r.json()).then(d=>{setItems(d.items);setMeta(d)}).catch(()=>setError('Could not connect to the API.'));
  useEffect(load,[category,search,start,end]);
  const upload=async e=>{const file=e.target.files[0]; if(!file)return; setBusy(true);setError('');const f=new FormData();f.append('file',file);const r=await fetch(`${API}/receipts`,{method:'POST',body:f});if(!r.ok){setError((await r.json()).detail||'Upload failed');}else load();setBusy(false);e.target.value='';};
  const update=async (id,cat)=>{await fetch(`${API}/receipts/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat})});load()};
  const selectedItems = Array.isArray(selected?.items) ? selected.items : [];
  return <main><header><div><span className="eyebrow">RECEIPT LEDGER</span><h1>Expense inbox</h1><p>Turn receipts into an organized, searchable ledger.</p></div><label className="upload">{busy?'Processing…':'+ Upload receipt'}<input type="file" accept="image/*,.pdf" onChange={upload} disabled={busy}/></label></header>
    {error&&<div className="error">{error}</div>}<section className="stats"><div><small>VISIBLE RECEIPTS</small><strong>{meta.count}</strong></div><div><small>VISIBLE TOTAL</small><strong>{formatCurrency(meta.total)}</strong></div><div><small>EXTRACTION</small><strong>Local-first</strong></div></section>
    <section className="toolbar"><input placeholder="Search merchant or filename…" value={search} onChange={e=>setSearch(e.target.value)}/><select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select><input type="date" value={start} onChange={e=>setStart(e.target.value)}/><input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></section>
    <section className="list">{items.length===0?<div className="empty">No receipts yet. Upload an image or PDF to get started.</div>:items.map(x=><article className="receipt" key={x.id} onClick={()=>setSelected(x)}><div className="icon">▧</div><div className="info"><b>{x.merchant}</b><span>{x.filename} · {x.receipt_date}</span></div><select value={x.category} onClick={e=>e.stopPropagation()} onChange={e=>update(x.id,e.target.value)}>{categories.slice(1).map(c=><option key={c}>{c}</option>)}</select><strong className="amount">{formatCurrency(x.amount)}</strong></article>)}</section>
    {selected&&<div className="detail"><button onClick={()=>setSelected(null)}>×</button><span className="eyebrow">RECEIPT DETAIL</span><h2>{selected.merchant}</h2><p>{selected.filename} · uploaded {new Date(selected.created_at).toLocaleString()}</p><p>Category: {selected.category}</p><div className="item-table"><div className="item-row item-header"><span>Item</span><span>Amount</span><span>Category</span></div>{selectedItems.length===0?<p className="items-empty">No line items extracted.</p>:selectedItems.map((item,index)=><div className="item-row" key={`${item.name}-${index}`}><span>{item.name}</span><span>{formatCurrency(item.amount)}</span><span>{item.category || selected.category}</span></div>)}</div><div className="detail-total"><span>Total</span><strong>{formatCurrency(selected.amount)} {selected.currency}</strong></div></div>}
  </main>
}
createRoot(document.getElementById('root')).render(<App/>);
