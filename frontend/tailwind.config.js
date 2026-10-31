/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'var(--color-bg-primary)',
          secondary: 'var(--color-bg-secondary)',
        },
        surface: {
          elevated: 'var(--color-surface-elevated)',
        },
        accent: {
          primary: 'var(--color-accent-primary)',
          secondary: 'var(--color-accent-secondary)',
          highlight: 'var(--color-accent-highlight)',
        },
        text: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          active: 'var(--color-border-active)',
        },
        status: {
          success: 'var(--color-success)',
          warning: 'var(--color-warning)',
          danger: 'var(--color-danger)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      boxShadow: {
        brutal: '3px 3px 0px 0px rgba(48, 48, 68, 0.9)',
        'brutal-accent': '3px 3px 0px 0px rgba(139, 92, 246, 0.9)',
        'brutal-cyan': '3px 3px 0px 0px rgba(0, 217, 255, 0.9)',
        'brutal-danger': '3px 3px 0px 0px rgba(239, 68, 68, 0.9)',
      },
      borderRadius: {
        none: '0px',
        sm: '2px',
        DEFAULT: '4px',
        md: '4px',
        lg: '6px',
      },
    },
  },
  plugins: [],
};

