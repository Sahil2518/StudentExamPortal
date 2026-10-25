/**
 * react-katex.d.ts
 * Type declarations for react-katex (no official @types package exists).
 */
declare module 'react-katex' {
  import { FC } from 'react'

  interface KaTeXProps {
    /** The LaTeX math string to render */
    math: string
    /** Optional CSS class for the wrapper element */
    className?: string
    /** Error handler; receives the Error object if KaTeX fails to parse */
    errorColor?: string
    renderError?: (error: Error) => React.ReactNode
  }

  /** Renders LaTeX math inline (within surrounding text flow) */
  export const InlineMath: FC<KaTeXProps>

  /** Renders LaTeX math as a display / block equation */
  export const BlockMath: FC<KaTeXProps>
}
