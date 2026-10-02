// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { TypographyControls } from './TypographyControls'
import { effectiveSize, normalizeDesign, type Design } from './ticketDesign'

afterEach(cleanup)

it('loads old designs with defaults and scales only automatic fields', () => {
  const design = normalizeDesign({safe_area:.08})
  expect(design.base_font_size).toBe(15)
  expect(design.font_family).toBe('barlow')
  design.text_styles.seat.font_size = 12
  design.base_font_size = 15
  expect(effectiveSize(design,'title')).toBe(28.5)
  expect(effectiveSize(design,'row')).toBe(15)
  expect(effectiveSize(design,'seat')).toBe(12)
})

it('updates individual styles, resets inheritance and switches labels', () => {
  let design = normalizeDesign()
  const onChange = (patch: Partial<Design>) => { design=normalizeDesign({...design,...patch});view.rerender(<TypographyControls design={design} onChange={onChange}/>) }
  const view = render(<TypographyControls design={design} onChange={onChange}/>)
  fireEvent.change(screen.getByLabelText('Sitzplatz Schriftgröße'),{target:{value:'14'}})
  fireEvent.change(screen.getByLabelText('Basis-Schriftgröße'),{target:{value:'15'}})
  expect(effectiveSize(design,'row')).toBe(15)
  expect(effectiveSize(design,'seat')).toBe(14)
  expect((screen.getByLabelText('Reihe Beschriftung') as HTMLInputElement).checked).toBe(true)
  fireEvent.click(screen.getByLabelText('Reihe Beschriftung'))
  expect(design.text_styles.row.show_label).toBe(false)
  fireEvent.change(screen.getByLabelText('Sitzplatz Schriftgröße'),{target:{value:''}})
  expect(effectiveSize(design,'seat')).toBe(15)
  fireEvent.change(screen.getByLabelText('Schriftart für alle Elemente'),{target:{value:'serif'}})
  expect(design.font_family).toBe('serif')
})
