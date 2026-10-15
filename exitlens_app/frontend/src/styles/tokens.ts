/**
 * ExitLens Design System Tokens
 * Strict adherence to the agreed visual token contract.
 */
export const tokens = {
  colors: {
    bgPage: '#F5F7FA',
    bgSurface: '#FFFFFF',
    textPrimary: '#172033',
    textSecondary: '#526176',
    textMuted: '#718096',
    border: '#E1E6EE',
    primaryAction: '#315BE8',
    primaryHover: '#2648C7',
    subtleBlue: '#EEF3FF',
    warningText: '#925C08',
    warningSurface: '#FFF5DE',
    failureText: '#B42318',
    failureSurface: '#FEF0F0',
    successText: '#18794E',
    successSurface: '#EAF7EF',
    neutralSurface: '#EEF1F5',
  },
  typography: {
    fontSans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue", Arial, sans-serif',
    fontMono: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
  },
  transitions: {
    subtle: '160ms cubic-bezier(0.16, 1, 0.3, 1)',
    drawer: '200ms cubic-bezier(0.16, 1, 0.3, 1)',
  },
} as const;

export type ColorToken = keyof typeof tokens.colors;
