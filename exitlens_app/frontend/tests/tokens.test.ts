import { describe, it, expect } from 'vitest';
import { tokens } from '../src/styles/tokens';

describe('Design Tokens System', () => {
  it('defines the required color palette according to specification', () => {
    expect(tokens.colors.bgPage).toBe('#F5F7FA');
    expect(tokens.colors.bgSurface).toBe('#FFFFFF');
    expect(tokens.colors.textPrimary).toBe('#172033');
    expect(tokens.colors.textSecondary).toBe('#526176');
    expect(tokens.colors.textMuted).toBe('#718096');
    expect(tokens.colors.border).toBe('#E1E6EE');
    expect(tokens.colors.primaryAction).toBe('#315BE8');
    expect(tokens.colors.primaryHover).toBe('#2648C7');
    expect(tokens.colors.subtleBlue).toBe('#EEF3FF');
    expect(tokens.colors.warningText).toBe('#925C08');
    expect(tokens.colors.warningSurface).toBe('#FFF5DE');
    expect(tokens.colors.failureText).toBe('#B42318');
    expect(tokens.colors.failureSurface).toBe('#FEF0F0');
    expect(tokens.colors.successText).toBe('#18794E');
    expect(tokens.colors.successSurface).toBe('#EAF7EF');
    expect(tokens.colors.neutralSurface).toBe('#EEF1F5');
  });
});
