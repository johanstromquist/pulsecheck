import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import ServiceCard from './ServiceCard';
import type { Service } from '../api/client';
import type { HealthCheckMessage } from '../hooks/useWebSocket';

// Mock the API client
vi.mock('../api/client', () => ({
  fetchHealthChecks: vi.fn().mockResolvedValue([]),
}));

const mockService: Service = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  name: 'Test Service',
  url: 'https://example.com',
  check_interval_seconds: 60,
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

function renderCard(realtimeCheck: HealthCheckMessage | null = null) {
  return render(
    <MemoryRouter>
      <ServiceCard service={mockService} realtimeCheck={realtimeCheck} />
    </MemoryRouter>,
  );
}

describe('ServiceCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders service name', () => {
    renderCard();
    expect(screen.getByText('Test Service')).toBeInTheDocument();
  });

  it('renders service URL', () => {
    renderCard();
    expect(screen.getByText('https://example.com')).toBeInTheDocument();
  });

  it('shows Unknown status when no checks available', () => {
    renderCard();
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('shows Healthy status from realtime check', () => {
    const realtimeCheck: HealthCheckMessage = {
      type: 'health_check',
      service_id: mockService.id,
      status: 'healthy',
      response_time_ms: 150,
      checked_at: '2024-01-01T12:00:00Z',
    };
    renderCard(realtimeCheck);
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });

  it('shows Down status from realtime check', () => {
    const realtimeCheck: HealthCheckMessage = {
      type: 'health_check',
      service_id: mockService.id,
      status: 'down',
      response_time_ms: null,
      checked_at: '2024-01-01T12:00:00Z',
    };
    renderCard(realtimeCheck);
    expect(screen.getByText('Down')).toBeInTheDocument();
  });

  it('shows Degraded status from realtime check', () => {
    const realtimeCheck: HealthCheckMessage = {
      type: 'health_check',
      service_id: mockService.id,
      status: 'degraded',
      response_time_ms: 5000,
      checked_at: '2024-01-01T12:00:00Z',
    };
    renderCard(realtimeCheck);
    expect(screen.getByText('Degraded')).toBeInTheDocument();
  });

  it('displays response time from realtime check', () => {
    const realtimeCheck: HealthCheckMessage = {
      type: 'health_check',
      service_id: mockService.id,
      status: 'healthy',
      response_time_ms: 250,
      checked_at: '2024-01-01T12:00:00Z',
    };
    renderCard(realtimeCheck);
    expect(screen.getByText('250 ms')).toBeInTheDocument();
  });

  it('links to service detail page', () => {
    renderCard();
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', `/services/${mockService.id}`);
  });
});
