import { describe, it, expect } from 'vitest';
import { env, validateEnvironment } from '@/config/env';

describe('Environment Configuration', () => {
  it('exposes defined environment properties with defaults', () => {
    expect(env.apiBaseUrl).toBeDefined();
    expect(typeof env.apiTimeout).toBe('number');
    expect(env.firebase).toBeDefined();
    expect(typeof env.firebase).toBe('object');
  });

  it('validateEnvironment provides diagnostic report without leaking secrets', () => {
    const report = validateEnvironment();
    expect(report).toHaveProperty('isConfigured');
    expect(report).toHaveProperty('missing');
    expect(report).toHaveProperty('configured');
    expect(Array.isArray(report.missing)).toBe(true);
    expect(Array.isArray(report.configured)).toBe(true);

    // Ensure report only returns variable names, not secret values
    report.missing.forEach((key) => {
      expect(typeof key).toBe('string');
      expect(key.startsWith('VITE_')).toBe(true);
    });
    report.configured.forEach((key) => {
      expect(typeof key).toBe('string');
      expect(key.startsWith('VITE_')).toBe(true);
    });
  });
});

