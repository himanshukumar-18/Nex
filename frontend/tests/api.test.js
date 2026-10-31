import { describe, it, expect, vi } from 'vitest';
import api from '@/services/api';

describe('API Client', () => {
  it('instantiates axios client with configured default timeout and base URL', () => {
    expect(api.client.defaults.timeout).toBe(15000);
    expect(api.client.defaults.headers['Content-Type']).toBe('application/json');
    expect(api.client.defaults.headers['Accept']).toBe('application/json');
  });

  it('exposes standard HTTP methods', () => {
    expect(typeof api.get).toBe('function');
    expect(typeof api.post).toBe('function');
    expect(typeof api.put).toBe('function');
    expect(typeof api.patch).toBe('function');
    expect(typeof api.delete).toBe('function');
  });
});

