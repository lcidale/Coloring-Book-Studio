import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge, PAGE_STATUS_LABELS } from '../badge'

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Approved</Badge>)
    expect(screen.getByText('Approved')).toBeInTheDocument()
  })

  it('applies data-slot="badge" attribute', () => {
    render(<Badge>Test</Badge>)
    expect(screen.getByText('Test').closest('[data-slot="badge"]')).toBeTruthy()
  })

  it('renders dot indicator when dot=true', () => {
    const { container } = render(<Badge dot>Idea</Badge>)
    // dot is an aria-hidden span with specific classes
    const dot = container.querySelector('[aria-hidden="true"]')
    expect(dot).toBeTruthy()
  })

  it('does not render dot when dot=false (default)', () => {
    const { container } = render(<Badge>No Dot</Badge>)
    expect(container.querySelector('[aria-hidden="true"]')).toBeNull()
  })

  it('accepts and forwards extra className', () => {
    render(<Badge className="my-custom-class">X</Badge>)
    const el = screen.getByText('X').closest('[data-slot="badge"]')
    expect(el).toHaveClass('my-custom-class')
  })

  it.each([
    'idea', 'prompt', 'generated', 'review',
    'revision', 'approved', 'print_ready', 'exported',
  ] as const)('renders variant=%s without throwing', (variant) => {
    expect(() => render(<Badge variant={variant}>{variant}</Badge>)).not.toThrow()
  })

  it.each([
    'green', 'blue', 'yellow', 'red', 'purple', 'gray',
  ] as const)('renders semantic color variant=%s', (variant) => {
    expect(() => render(<Badge variant={variant}>{variant}</Badge>)).not.toThrow()
  })
})

describe('PAGE_STATUS_LABELS', () => {
  it('has a human-readable label for every PageStatus', () => {
    const statuses = [
      'idea', 'prompt', 'generated', 'review',
      'revision', 'approved', 'print_ready', 'exported',
    ] as const
    for (const s of statuses) {
      expect(PAGE_STATUS_LABELS[s]).toBeTruthy()
    }
  })

  it('maps print_ready to "Print Ready"', () => {
    expect(PAGE_STATUS_LABELS.print_ready).toBe('Print Ready')
  })

  it('maps approved to "Approved"', () => {
    expect(PAGE_STATUS_LABELS.approved).toBe('Approved')
  })
})
