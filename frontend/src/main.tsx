import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Film, Search, ImagePlus, Printer, Settings, Clock3, Download, RefreshCw, Plus, Check, Wifi, ChevronRight, RotateCcw } from 'lucide-react'
import './style.css'
import './preview.css'
import { usePreview } from './usePreview'

type Crop = { zoom: number; x: number; y: number }
type Design = { readability: 'minimal'|'soft'|'strong'|'auto'; text_color: 'auto'|'white'|'black'; shadow: 'off'|'light'|'strong'; position: 'bottom-left'|'bottom-center'|'bottom-right'; strength: number; safe_area: number }
type Ticket = { id?: string; title: string; tmdb_id: number|null; poster_path: string|null; asset_id: string|null; date: string; time: string; cinema: string; hall: string; row: string; seat: string; format: string; note: string; crop: Crop; design: Design }
type Movie = { id: number; title: string; release_date?: string; poster_path?: string }
type Poster = { file_path: string; iso_639_1: string|null; width: number; height: number }
type Job = { id: string; ticket_id: string|null; status: string; error: string|null; created_at: string }
type PrinterStatus = { ready: boolean; backend: string; bluetooth: { adapter_available: boolean; device_known: boolean; paired: boolean; trusted: boolean; connected: boolean }; obexftp: { available: boolean; channel: number } }
const empty: Ticket = { title: '', tmdb_id: null, poster_path: null, asset_id: null, date: '', time: '', cinema: '', hall: '', row: '', seat: '', format: '', note: '', crop: { zoom: 1, x: 0, y: 0 }, design: { readability: 'soft', text_color: 'auto', shadow: 'light', position: 'bottom-left', strength: .5, safe_area: .065 } }
const img = (path?: string|null, size='w342') => path ? `https://image.tmdb.org/t/p/${size}${path}` : ''
const getToken = () => sessionStorage.getItem('viju-admin') || ''
async function api<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + url, { ...init, headers: { ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), 'X-Admin-Token': getToken(), ...init.headers } })
  if (!response.ok) {
    let detail = response.statusText
    try { const data = await response.json(); detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail) } catch { /* Keep HTTP status */ }
    throw Error(`${response.status}: ${detail}`)
  }
  return response.json()
}
function App() {
  const [page, setPage] = useState<'editor'|'history'|'settings'>('editor')
  const [ticket, setTicket] = useState<Ticket>(() => { try { return { ...empty, ...JSON.parse(sessionStorage.getItem('viju-draft') || '{}') } } catch { return empty } })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Movie[]>([])
  const [now, setNow] = useState<Movie[]>([])
  const [posters, setPosters] = useState<Poster[]>([])
  const [searching, setSearching] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [history, setHistory] = useState<Ticket[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [printer, setPrinter] = useState<PrinterStatus|null>(null)
  const [printerForm, setPrinterForm] = useState({ mac: '', channel: 4 })
  const [network, setNetwork] = useState<Record<string, unknown>|null>(null)
  const [wifi, setWifi] = useState({ ssid: '', password: '' })
  const [presets, setPresets] = useState<{id: string; name: string; design: Design}[]>([])
  const [presetName, setPresetName] = useState('')
  const [token, setToken] = useState(getToken())
  const uploadRef = useRef<HTMLInputElement>(null)
  const previewRef = useRef<HTMLImageElement>(null)
  const drag = useRef<{x: number; y: number; crop: Crop}|null>(null)
  const movieController = useRef<AbortController | null>(null)
  const previewState = usePreview(ticket, token, Boolean(ticket.poster_path || ticket.asset_id))
  const preview = previewState.url
  const patch = (p: Partial<Ticket>) => setTicket(old => ({...old, ...p}))
  const design = (p: Partial<Design>) => patch({ design: {...ticket.design, ...p} })
  const crop = (p: Partial<Crop>) => patch({ crop: {...ticket.crop, ...p} })
  const report = (error: unknown) => setNotice(error instanceof Error ? error.message : String(error))
  const refresh = () => {
    api<Ticket[]>('/tickets').then(setHistory).catch(report)
    api<Job[]>('/print-jobs').then(setJobs).catch(report)
    api<PrinterStatus>('/printer/status').then(setPrinter).catch(report)
  }
  useEffect(() => {
    if (!getToken()) setNotice('Trage unter Einstellungen zuerst das Admin-Token aus der Installation ein.')
    refresh()
    api<Movie[]>('/movies/now-playing').then(setNow).catch(() => {})
    api<{mac:string;channel:number}>('/printer').then(setPrinterForm).catch(() => {})
    api('/network/status').then(x => setNetwork(x as Record<string, unknown>)).catch(() => {})
    api<typeof presets>('/presets').then(setPresets).catch(() => {})
    const timer = setInterval(() => api<Job[]>('/print-jobs').then(setJobs).catch(() => {}), 4000)
    return () => clearInterval(timer)
  }, [])
  useEffect(() => {
    sessionStorage.setItem('viju-draft', JSON.stringify(ticket))
  }, [ticket])
  useEffect(() => () => movieController.current?.abort(), [])
  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); setSearching(false); return }
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const response = await fetch('/api/movies/search?q=' + encodeURIComponent(query), { signal: controller.signal })
        if (!response.ok) throw Error('Filmsuche nicht verfügbar')
        setResults(await response.json())
      } catch (e) { if (!controller.signal.aborted) report(e) }
      finally { if (!controller.signal.aborted) setSearching(false) }
    }, 400)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])
  async function selectMovie(movie: Movie) {
    movieController.current?.abort()
    const controller = new AbortController()
    movieController.current = controller
    setQuery(''); setResults([]); setNotice('')
    setPosters([])
    patch({ title: movie.title, tmdb_id: movie.id, poster_path: movie.poster_path || null, asset_id: null, crop: {zoom:1,x:0,y:0} })
    try {
      const gallery = await api<Poster[]>(`/movies/${movie.id}/posters`, { signal: controller.signal })
      if (controller.signal.aborted) return
      setPosters(gallery)
      patch({ title: movie.title, tmdb_id: movie.id, poster_path: gallery[0]?.file_path || movie.poster_path || null, asset_id: null, crop: {zoom:1,x:0,y:0} })
    } catch (e) { if (!controller.signal.aborted) report(e) }
  }
  async function upload(file?: File) {
    if (!file) return
    movieController.current?.abort()
    setBusy(true)
    try {
      const body = new FormData(); body.append('file', file)
      const result = await api<{id:string}>('/uploads/images', {method:'POST', body})
      patch({ asset_id: result.id, poster_path: null, tmdb_id: null, crop:{zoom:1,x:0,y:0} })
      setPosters([]); setNotice('Bild geladen.')
    } catch(e) { report(e) } finally { setBusy(false) }
  }
  async function save() {
    const result = await api<Ticket>(ticket.id ? `/tickets/${ticket.id}` : '/tickets', {method: ticket.id ? 'PUT':'POST', body: JSON.stringify(ticket)})
    patch({id:result.id}); refresh(); setNotice('Ticket gespeichert.')
    return result.id!
  }
  async function act(fn: () => Promise<unknown>) { setBusy(true); setNotice(''); try { await fn() } catch(e) { report(e) } finally { setBusy(false) } }
  function print() { act(async () => { const id = await save(); const key = crypto.randomUUID(); const job = await api<Job>(`/tickets/${id}/print`, {method:'POST', headers:{'Idempotency-Key':key}}); setNotice('Druckauftrag erstellt: ' + job.id.slice(0,8)); refresh() }) }
  function renderFile(format: 'png'|'jpeg') { act(async () => { const id = await save(); await api(`/tickets/${id}/render`, {method:'POST'}); window.open(`/api/renders/${id}?format=${format}`, '_blank', 'noopener') }) }
  function handleMove(e: React.PointerEvent) {
    if (!drag.current || !previewRef.current) return
    const rect = previewRef.current.getBoundingClientRect()
    const factor = 1.8 / Math.max(.5, ticket.crop.zoom)
    crop({x:Math.max(-1,Math.min(1,drag.current.crop.x - (e.clientX-drag.current.x)/rect.width*factor)), y:Math.max(-1,Math.min(1,drag.current.crop.y - (e.clientY-drag.current.y)/rect.height*factor))})
  }
  const activePoster = ticket.asset_id ? `/api/assets/${ticket.asset_id}` : img(ticket.poster_path, 'w500')
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Film size={25}/></div><div><strong>ViJu<span>TicketBooth</span></strong><small>DEIN KINO. DEIN TICKET.</small></div></div>
      <nav><button className={page==='editor'?'active':''} onClick={()=>setPage('editor')}><Plus size={19}/> Ticket erstellen</button><button className={page==='history'?'active':''} onClick={()=>{setPage('history');refresh()}}><Clock3 size={19}/> Historie</button><button className={page==='settings'?'active':''} onClick={()=>setPage('settings')}><Settings size={19}/> Einstellungen</button></nav>
      <div className="side-foot"><span className={printer?.ready?'status-dot good':'status-dot'}/><div><b>{printer?.backend==='mock'?'Mock-Drucker':printer?.ready?'Drucker bereit':'Drucker prüfen'}</b><small>{printer?.backend==='mock'?'Druckdateien werden gespeichert':'HP Sprocket'}</small></div></div>
    </aside>
    <main>
      <header><div><span className="eyebrow">VIJU / {page==='editor'?'STUDIO':page==='history'?'SAMMLUNG':'KONFIGURATION'}</span><h1>{page==='editor'?'Ein Film. Ein Moment. Dein Ticket.':page==='history'?'Deine Tickets':'Einstellungen'}</h1><p>{page==='editor'?'Gestalte ein kleines Stück Kino für die Ewigkeit.':page==='history'?'Vergangene Erinnerungen wiederfinden und erneut drucken.':'Drucker, WLAN und Zugriff verwalten.'}</p></div><div className="header-mark">VT<span>•</span>01</div></header>
      {notice && <div className="notice" role="status">{notice}<button onClick={()=>setNotice('')}>×</button></div>}
      {page==='editor' && <div className="workspace">
        <section className="controls">
          <article className="panel"><div className="section-title"><span className="number">01</span><div><h2>Der Film</h2><p>Wähle einen Film oder beginne frei.</p></div></div>
            <div className="searchbox"><Search size={19}/><input aria-label="Film suchen" placeholder="Filmtitel suchen …" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&results[0]) selectMovie(results[0]);if(e.key==='Escape')setResults([])}}/>{searching&&<span className="spinner"/>}</div>
            {results.length>0 && <div className="results">{results.map(m=><button key={m.id} onClick={()=>selectMovie(m)}>{m.poster_path?<img src={img(m.poster_path,'w92')} alt=""/>:<span className="mini-blank"/>}<span><b>{m.title}</b><small>{m.release_date?.slice(0,4)||'–'}</small></span><ChevronRight size={16}/></button>)}</div>}
            {now.length>0&&!query&&<><div className="subhead">AKTUELL IM KINO <button onClick={()=>act(async()=>selectMovie(await api<Movie>('/movies/random')))}>Zufallsfilm ↗</button></div><div className="movie-strip">{now.filter(m=>m.poster_path).slice(0,12).map(m=><button key={m.id} onClick={()=>selectMovie(m)} title={m.title}><img src={img(m.poster_path,'w185')} alt={m.title}/></button>)}</div></>}
            <div className="split-actions"><button className="text-action" onClick={()=>{movieController.current?.abort();patch({tmdb_id:null,poster_path:null,asset_id:null,title:''});setPosters([])}}><Plus size={16}/> Eigener Filmtitel</button><button className="text-action" onClick={()=>uploadRef.current?.click()}><ImagePlus size={16}/> Bild hochladen</button></div>
            <input ref={uploadRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e=>upload(e.target.files?.[0])}/>
            <label className="field">Filmtitel<input value={ticket.title} maxLength={160} placeholder="z. B. Dune: Part Two" onChange={e=>patch({title:e.target.value})}/></label>
            {posters.length>0&&<><div className="subhead">POSTER AUSWÄHLEN <small>ENGLISH FIRST</small></div><div className="poster-strip">{posters.map((p,i)=><button key={p.file_path} className={ticket.poster_path===p.file_path?'selected':''} onClick={()=>patch({poster_path:p.file_path,asset_id:null,crop:{zoom:1,x:0,y:0}})} title={`${p.iso_639_1||'ohne Sprache'} · ${p.width} × ${p.height}`}><img loading="lazy" src={img(p.file_path,'w185')} alt={`Poster ${i+1}`}/><span>{p.iso_639_1||'–'}</span></button>)}</div></>}
          </article>
          <article className="panel"><div className="section-title"><span className="number">02</span><div><h2>Die Details</h2><p>Alle Angaben sind optional.</p></div></div>
            <div className="form-grid">{([['date','Datum','date'],['time','Uhrzeit','time'],['cinema','Kino','text'],['hall','Saal','text'],['row','Reihe','text'],['seat','Sitz','text'],['format','Vorstellungsart','text'],['note','Zusatztext','text']] as const).map(([key,label,type])=><label className="field" key={key}>{label}<input type={type} value={ticket[key]} maxLength={key==='note'?120:80} onChange={e=>patch({[key]:e.target.value})}/></label>)}</div>
          </article>
          <article className="panel"><div className="section-title"><span className="number">03</span><div><h2>Der Look</h2><p>Text direkt auf dem Filmplakat.</p></div></div>
            <label className="field">Lesbarkeit<div className="segmented">{(['minimal','soft','strong','auto'] as const).map(v=><button key={v} className={ticket.design.readability===v?'selected':''} onClick={()=>design({readability:v})}>{v}</button>)}</div></label>
            <div className="form-grid"><label className="field">Textfarbe<select value={ticket.design.text_color} onChange={e=>design({text_color:e.target.value as Design['text_color']})}><option value="auto">Automatisch</option><option value="white">Weiß</option><option value="black">Schwarz</option></select></label><label className="field">Schatten<select value={ticket.design.shadow} onChange={e=>design({shadow:e.target.value as Design['shadow']})}><option value="off">Aus</option><option value="light">Leicht</option><option value="strong">Stark</option></select></label></div>
            <label className="field">Textposition<select value={ticket.design.position} onChange={e=>design({position:e.target.value as Design['position']})}><option value="bottom-left">Unten links</option><option value="bottom-center">Unten mittig</option><option value="bottom-right">Unten rechts</option></select></label>
            <label className="field">Overlay-Stärke <span>{Math.round(ticket.design.strength*100)}%</span><input type="range" min="0" max="1" step=".05" value={ticket.design.strength} onChange={e=>design({strength:+e.target.value})}/></label>
            <label className="field">Sicherheitsabstand <span>{Math.round(ticket.design.safe_area*100)}%</span><input type="range" min=".03" max=".15" step=".005" value={ticket.design.safe_area} onChange={e=>design({safe_area:+e.target.value})}/></label>
            <label className="field">Poster-Zoom <span>{Math.round(ticket.crop.zoom*100)}%</span><input type="range" min="1" max="4" step=".05" value={ticket.crop.zoom} onChange={e=>crop({zoom:+e.target.value})}/></label>
            <button className="text-action" onClick={()=>patch({crop:{zoom:1,x:0,y:0}})}><RotateCcw size={16}/> Bildausschnitt zurücksetzen</button>
            <div className="preset-row"><select aria-label="Preset wählen" defaultValue="" onChange={e=>{const preset=presets.find(p=>p.id===e.target.value);if(preset)design(preset.design)}}><option value="">Preset wählen</option>{presets.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><input aria-label="Presetname" placeholder="Neues Preset" value={presetName} onChange={e=>setPresetName(e.target.value)}/><button onClick={()=>act(async()=>{await api('/presets',{method:'POST',body:JSON.stringify({name:presetName,design:ticket.design})});setPresets(await api('/presets'));setPresetName('')})}>Speichern</button></div>
          </article>
        </section>
        <section className="preview-side"><div className="preview-panel"><div className="preview-heading"><div><span className="eyebrow">LIVE-VORSCHAU</span><h2>Dein Sammlerstück</h2></div><span className="format-tag">2 × 3 FORMAT</span></div>
          <div className="ticket-stage"><div className="ticket-image" onPointerDown={e=>{if(!activePoster)return;drag.current={x:e.clientX,y:e.clientY,crop:{...ticket.crop}};e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={handleMove} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null}>
            {preview?<img ref={previewRef} src={preview} alt="Exakte Druckvorschau"/>:activePoster?<div className="loading-preview"><img ref={previewRef} src={activePoster} alt="Ausgewähltes Poster"/><span role={previewState.error?'alert':'status'}>{previewState.error || 'Vorschau wird gerendert …'}</span></div>:<div className="empty-preview"><Film size={48}/><strong>Die Leinwand wartet.</strong><span>Wähle einen Film oder lade dein eigenes Poster hoch.</span></div>}
          </div></div><p className="preview-hint">Poster ziehen, um den Bildausschnitt zu verschieben. Die Vorschau stammt aus dem Druckrenderer.</p>
          <div className="print-actions"><button className="primary" disabled={busy||!activePoster} onClick={print}><Printer size={18}/>{busy?'Bitte warten …':'Ticket drucken'}</button><button disabled={busy||!activePoster} onClick={()=>act(save)}><Check size={18}/> Speichern</button></div><div className="download-actions"><button disabled={!activePoster} onClick={()=>renderFile('png')}><Download size={15}/> PNG</button><button disabled={!activePoster} onClick={()=>renderFile('jpeg')}><Download size={15}/> JPEG</button></div>
        </div></section>
      </div>}
      {page==='history'&&<div className="page-panel"><div className="list-heading"><h2>Gespeicherte Tickets</h2><button onClick={refresh}><RefreshCw size={16}/> Aktualisieren</button></div>{history.length===0?<p className="muted">Noch keine Tickets gespeichert.</p>:<div className="ticket-list">{history.map(t=><div className="history-item" key={t.id}><img src={t.asset_id?`/api/assets/${t.asset_id}`:img(t.poster_path,'w92')} alt=""/><div><strong>{t.title||'Ohne Titel'}</strong><small>{[t.date,t.time,t.cinema].filter(Boolean).join(' · ')||'Ohne Vorstellungsdaten'}</small></div><button onClick={()=>{setTicket(t);setPage('editor')}}>Öffnen</button><button onClick={()=>act(async()=>{const copy=await api<Ticket>(`/tickets/${t.id}/duplicate`,{method:'POST'});setTicket(copy);setPage('editor');refresh()})}>Duplizieren</button></div>)}</div>}
        <div className="list-heading jobs-title"><h2>Druckaufträge</h2></div>{jobs.map(j=><div className="job-item" key={j.id}><span className={`job-state ${j.status}`}>{j.status}</span><div><b>#{j.id.slice(0,8)}</b><small>{new Date(j.created_at).toLocaleString('de-DE')} {j.error&&'· '+j.error}</small></div>{(j.status==='failed'||j.status==='completed')&&j.ticket_id&&<button onClick={()=>act(async()=>{await api(`/print-jobs/${j.id}/retry`,{method:'POST'});refresh()})}>Erneut drucken</button>}</div>)}</div>}
      {page==='settings'&&<div className="settings-grid">
        <article className="panel"><div className="section-title"><span className="number"><Printer size={18}/></span><div><h2>HP Sprocket</h2><p>MAC-Adresse manuell eintragen. Kein Bluetooth-Scan.</p></div></div><div className="form-grid"><label className="field">Bluetooth-MAC<input placeholder="C4:30:18:38:BD:E1" value={printerForm.mac} onChange={e=>setPrinterForm({...printerForm,mac:e.target.value})}/></label><label className="field">OBEX-Channel<input type="number" min="1" max="30" value={printerForm.channel} onChange={e=>setPrinterForm({...printerForm,channel:+e.target.value})}/></label></div><div className="button-row"><button onClick={()=>act(async()=>{await api('/printer',{method:'PUT',body:JSON.stringify(printerForm)});setPrinter(await api('/printer/status'));setNotice('Drucker gespeichert.')})}>Speichern</button><button onClick={()=>act(async()=>setPrinter(await api('/printer/status')))}>Status prüfen</button><button onClick={()=>act(async()=>{await api('/printer/setup',{method:'POST'});setPrinter(await api('/printer/status'))})}>Pairing</button><button onClick={()=>act(async()=>{await api('/printer/trust',{method:'POST'});setPrinter(await api('/printer/status'))})}>Vertrauen</button><button onClick={()=>act(async()=>{const job=await api<Job>('/printer/test-print',{method:'POST'});setNotice('Testdruck: '+job.id.slice(0,8));refresh()})}>Testdruck</button></div>{printer&&<div className="diagnostics">{[['Backend',printer.backend],['Adapter',printer.bluetooth.adapter_available],['Gerät bekannt',printer.bluetooth.device_known],['Gepaart',printer.bluetooth.paired],['Vertrauenswürdig',printer.bluetooth.trusted],['obexftp',printer.obexftp.available],['Bereit',printer.ready]].map(([label,value])=><div key={String(label)}><span>{label}</span><b>{typeof value==='boolean'?(value?'Ja':'Nein'):value}</b></div>)}</div>}<button className="danger-link" onClick={()=>act(async()=>{await api('/printer/forget',{method:'POST'});setPrinterForm({mac:'',channel:4});setPrinter(await api('/printer/status'))})}>Drucker aus ViJu-TicketBooth entfernen</button></article>
        <article className="panel"><div className="section-title"><span className="number"><Wifi size={18}/></span><div><h2>Netzwerk</h2><p>Setup und Recovery über den internen WLAN-Chip.</p></div></div><div className="diagnostics"><div><span>Modus</span><b>{String(network?.mode||'Nicht verfügbar')}</b></div><div><span>SSID</span><b>{String(network?.ssid||'–')}</b></div><div><span>IP-Adresse</span><b>{String(network?.ip_address||'–')}</b></div></div><label className="field">Neue WLAN-SSID<input autoComplete="off" value={wifi.ssid} onChange={e=>setWifi({...wifi,ssid:e.target.value})}/></label><label className="field">WLAN-Passwort<input type="password" autoComplete="new-password" value={wifi.password} onChange={e=>setWifi({...wifi,password:e.target.value})}/></label><button onClick={()=>act(async()=>{await api('/network/connect',{method:'POST',body:JSON.stringify(wifi)});setWifi({ssid:'',password:''});setNotice('Verbindungswechsel gestartet. Verbinde dein Gerät anschließend mit dem Heim-WLAN. Bei Fehlschlag kehrt das Setup-WLAN zurück.')})}>WLAN verbinden</button><p className="help">Beim Wechsel unterbricht das Pi-WLAN kurz. Bei einem falschen Passwort startet der Setup-AP erneut.</p></article>
        <article className="panel"><div className="section-title"><span className="number">✦</span><div><h2>Admin-Zugang</h2><p>Für Speichern, Drucken und Einstellungen.</p></div></div><label className="field">Admin-Token<input type="password" value={token} onChange={e=>setToken(e.target.value)}/></label><button onClick={()=>{sessionStorage.setItem('viju-admin',token);setNotice('Token für diese Browser-Sitzung gespeichert.')}}>Token übernehmen</button><p className="help">Das Token steht in der bei der Installation angelegten Zugangsdaten-Datei auf dem Pi.</p></article>
      </div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
