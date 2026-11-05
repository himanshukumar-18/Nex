import { describe, it, expect, vi, beforeEach } from 'vitest';
import systemApi from '@/services/systemApi';
import api from '@/services/api';

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('systemApi Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getLiveness calls GET /health/ with root baseURL', async () => {
    const mockData = { status: 'ok' };
    api.get.mockResolvedValueOnce({ data: mockData });

    const result = await systemApi.getLiveness();
    expect(api.get).toHaveBeenCalledWith('/health/', { baseURL: '' });
    expect(result).toEqual(mockData);
  });

  it('getReadiness calls GET /health/ready/ with root baseURL', async () => {
    const mockData = { status: 'ready', database: 'connected' };
    api.get.mockResolvedValueOnce({ data: mockData });

    const result = await systemApi.getReadiness();
    expect(api.get).toHaveBeenCalledWith('/health/ready/', { baseURL: '' });
    expect(result).toEqual(mockData);
  });

  it('propagates error when health endpoint fails', async () => {
    api.get.mockRejectedValueOnce(new Error('Network error'));
    await expect(systemApi.getLiveness()).rejects.toThrow('Network error');
  });
});

