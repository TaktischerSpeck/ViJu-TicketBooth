import { effectiveSize, labelsEnabled, textFields, type Design, type TextKey, type TextStyle } from './ticketDesign'

type Props = { design: Design; onChange: (patch: Partial<Design>) => void }
export function TypographyControls({design, onChange}: Props) {
  function update(key: TextKey, patch: Partial<TextStyle>) {
    onChange({text_styles: {...design.text_styles, [key]: {...design.text_styles[key], ...patch}}})
  }
  return <div className="typography-controls">
    <div className="form-grid">
      <label className="field">Schriftart für alle Elemente<select value={design.font_family} onChange={e=>onChange({font_family:e.target.value as Design['font_family']})}>
        <option value="barlow">Barlow Condensed</option><option value="sans">DejaVu Sans</option><option value="serif">DejaVu Serif</option><option value="mono">DejaVu Sans Mono</option>
      </select></label>
      <label className="field">Basis-Schriftgröße<input aria-label="Basis-Schriftgröße" type="number" min="4" max="24" step=".5" value={design.base_font_size} onChange={e=>{const n=Number(e.target.value);if(n>=4&&n<=24)onChange({base_font_size:n})}}/></label>
    </div>
    <p className="help">Automatische Größen wachsen mit der Basis. Titel: 190 %, Datum/Kino/Zusatztext: 80 %, übrige Angaben: 100 %. Eine eigene Größe bleibt fest. Größen sind Layout-Einheiten; der Druckrand verkleinert das gesamte Ticket.</p>
    <div className="text-style-list">{textFields.map(([key,label])=>{
      const style = design.text_styles[key]
      return <div className="text-style-item" key={key}>
        <b>{label}</b>
        <label className="field">Größe {style.font_size===null&&<small>Auto: {Number(effectiveSize(design,key).toFixed(1))}</small>}
          <input aria-label={label+' Schriftgröße'} type="number" min="4" max="48" step=".5" value={style.font_size??''} placeholder="Automatisch" onChange={e=>{const n=Number(e.target.value);if(!e.target.value)update(key,{font_size:null});else if(n>=4&&n<=48)update(key,{font_size:n})}}/>
        </label>
        <label className="field">Schriftstärke<select aria-label={label+' Schriftstärke'} value={style.bold===null?'auto':style.bold?'bold':'regular'} onChange={e=>update(key,{bold:e.target.value==='auto'?null:e.target.value==='bold'})}>
          <option value="auto">Automatisch</option><option value="regular">Normal</option><option value="bold">Fett</option>
        </select></label>
        {key!=='title'&&<label className="toggle-label"><input type="checkbox" aria-label={label+' Beschriftung'} checked={labelsEnabled(design,key)} onChange={e=>update(key,{show_label:e.target.checked})}/> Beschriftung</label>}
        <button className="text-action" onClick={()=>update(key,{font_size:null,bold:null,show_label:null})}>Automatisch</button>
      </div>
    })}</div>
  </div>
}
