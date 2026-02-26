import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import type { Service } from '../api/client';

const mockServices: Service[] = [
  {
    id: '111',
    name: 'API Gateway',
    url: 'https://api.example.com',
    check_interval_seconds: 30,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '222',
    name: 'Web Frontend',
    url: 'https://www.example.com',
    check_interval_seconds: 60,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

// Mock modules
vi.mock('../api/client', () => ({
  fetchServices: vi.fn(),
  fetchHealthChecks: vi.fn().mockResolvedValue([]),
  createService: vi.fn(),
}));

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({ connected: true }),
}));

import { fetchServices } from '../api/client';

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(() => {}), // never resolves
    );
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders services after loading', async () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockResolvedValue(mockServices);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('API Gateway')).toBeInTheDocument();
    });
    expect(screen.getByText('Web Frontend')).toBeInTheDocument();
  });

  it('shows empty state when no services', async () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/no services yet/i)).toBeInTheDocument();
    });
  });

  it('renders PulseCheck heading', async () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('PulseCheck')).toBeInTheDocument();
  });

  it('shows live connection indicator', async () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('has link to incidents page', async () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Incidents')).toBeInTheDocument();
  });

  it('has link to status page', async () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Status Page')).toBeInTheDocument();
  });

  it('has add service button', async () => {
    (fetchServices as ReturnType<typeof vi.fn>).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('+ Add Service')).toBeInTheDocument();
  });
});
