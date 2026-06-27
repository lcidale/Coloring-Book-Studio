import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatCard } from '../stat-card'

describe('StatCard', () => {
  it('renders the label', () => {
    render(<StatCard label="Active Books" value={5} />)
    expect(screen.getByText('Active Books')).toBeInTheDocument()
  })

  it('renders a numeric value', () => {
    render(<StatCard label="Pages" value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders a string value', () => {
    render(<StatCard label="Status" value="Ready" />)
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('renders optional sub text when provided', () => {
    render(<StatCard label="Books" value={3} sub="this week" />)
    expect(screen.getByText('this week')).toBeInTheDocument()
  })

  it('does not render sub element when sub is omitted', () => {
    const { container } = render(<StatCard label="Books" value={3} />)
    // There should be only 2 <p> elements: label and value
    const paragraphs = container.querySelectorAll('p')
    expect(paragraphs).toHaveLength(2)
  })

  it('has data-slot="stat-card" on the root element', () => {
    const { container } = render(<StatCard label="Label" value={0} />)
    expect(container.querySelector('[data-slot="stat-card"]')).toBeTruthy()
  })

  it('forwards extra className to root element', () => {
    const { container } = render(<StatCard label="L" value={1} className="extra-class" />)
    expect(container.querySelector('[data-slot="stat-card"]')).toHaveClass('extra-class')
  })

  it('renders ReactNode as value (e.g. a span)', () => {
    render(
      <StatCard
        label="Custom"
        value={<span data-testid="custom-val">100%</span>}
      />
    )
    expect(screen.getByTestId('custom-val')).toBeInTheDocument()
  })
})
