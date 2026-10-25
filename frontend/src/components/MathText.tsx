/**
 * components/MathText.tsx
 * Smart math rendering component using KaTeX.
 * Detects LaTeX delimiters ($...$, $$...$$) and renders them via KaTeX,
 * falling back to plain text for non-math content.
 * Supports inline math ($...$) and display/block math ($$...$$).
 */
import React from 'react'
import { InlineMath, BlockMath } from 'react-katex'

interface MathTextProps {
  /** The text to render, which may contain LaTeX math delimiters */
  text: string
  /** Additional CSS classes for the container span */
  className?: string
}

type Segment = { type: 'text' | 'inline' | 'block'; content: string }

/**
 * Splits a string into alternating plain-text and LaTeX-math segments.
 * Block math ($$...$$) is matched first to avoid conflicts with inline ($...$).
 */
function parseMathSegments(text: string): Segment[] {
  const segments: Segment[] = []
  // Match $$...$$ (block) OR $...$ (inline), block has priority
  const pattern = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }
    const raw = match[0]
    if (raw.startsWith('$$')) {
      segments.push({ type: 'block', content: raw.slice(2, -2) })
    } else {
      segments.push({ type: 'inline', content: raw.slice(1, -1) })
    }
    lastIndex = match.index + raw.length
  }

  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) })
  }
  if (segments.length === 0) {
    segments.push({ type: 'text', content: text })
  }
  return segments
}

/**
 * Renders text that may contain LaTeX math expressions.
 * Block math ($$...$$) renders centred on its own line.
 * Inline math ($...$) flows within the surrounding text.
 * Plain text is rendered as-is.
 */
export default function MathText({ text, className }: MathTextProps) {
  if (!text) return null

  const segments = parseMathSegments(text)

  // If the whole string is plain text, render simply
  if (segments.length === 1 && segments[0].type === 'text') {
    return <span className={className}>{text}</span>
  }

  return (
    <span className={className}>
      {segments.map((seg, i) => {
        if (seg.type === 'block') {
          return (
            <span key={i} className="block my-2">
              <BlockMath math={seg.content} />
            </span>
          )
        }
        if (seg.type === 'inline') {
          return <InlineMath key={i} math={seg.content} />
        }
        return <span key={i}>{seg.content}</span>
      })}
    </span>
  )
}
