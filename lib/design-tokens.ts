/**
 * SpecIndex design tokens. See docs/design-system.md
 */

export const colors = {
  bg: "#FAFAF9",
  ink: "#1A1A1A",
  white: "#FFFFFF",
  amber: "#F59E0B",
  amberHover: "#D97706",
  green: "#166534",
  greenLight: "#DCFCE7",
  gray100: "#F5F5F4",
  gray200: "#E7E5E4",
  gray400: "#A8A29E",
  gray600: "#57534E",
  gray700: "#44403C",
  border: "#E7E5E4",
} as const;

export const fonts = {
  sans: "var(--font-geist-sans)",
  mono: "var(--font-geist-mono)",
} as const;

export const radii = {
  button: "0.5rem",
  card: "0.75rem",
  pill: "9999px",
} as const;
