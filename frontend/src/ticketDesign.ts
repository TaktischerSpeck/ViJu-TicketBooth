export const textFields = [
  ['title', 'Filmtitel'], ['time', 'Uhrzeit'], ['hall', 'Saal'], ['row', 'Reihe'],
  ['seat', 'Sitzplatz'], ['date', 'Datum'],
  ['cinema', 'Kino'], ['note', 'Zusatztext'],
] as const
export type TextKey = typeof textFields[number][0]
export type TextStyle = { font_size: number | null; bold: boolean | null; show_label: boolean | null }
export type Design = {
  readability: 'minimal'|'soft'|'strong'|'auto'; text_color: 'auto'|'white'|'black'
  shadow: 'off'|'light'|'strong'; position: 'bottom-left'|'bottom-center'|'bottom-right'
  strength: number; safe_area: number; print_inset: number
  font_family: 'barlow'|'sans'|'serif'|'mono'; base_font_size: number
  text_styles: Record<TextKey, TextStyle>
}
export const defaultStyle: TextStyle = { font_size: null, bold: null, show_label: null }
export function normalizeDesign(value: Partial<Design> = {}): Design {
  return {
    readability: 'soft', text_color: 'auto', shadow: 'light', position: 'bottom-left',
    strength: .5, safe_area: .065, print_inset: .03, font_family: 'barlow', base_font_size: 15,
    ...value,
    text_styles: Object.fromEntries(textFields.map(([key]) => [
      key, {...defaultStyle, ...value.text_styles?.[key]},
    ])) as Record<TextKey, TextStyle>,
  }
}
export function effectiveSize(design: Design, key: TextKey): number {
  const ratio = key === 'title' ? 1.9 : ['date', 'cinema', 'note'].includes(key) ? .8 : 1
  return design.text_styles[key].font_size ?? design.base_font_size * ratio
}
export function labelsEnabled(design: Design, key: TextKey): boolean {
  return design.text_styles[key].show_label ?? ['hall', 'row', 'seat'].includes(key)
}
