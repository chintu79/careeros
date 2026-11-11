import { render, screen, fireEvent, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import LandingPage from '../landing/LandingPage';

afterEach(() => {
  document.title = '';
  delete document.documentElement.dataset.page;
});

describe('LandingPage', () => {
  it('renders the hero, project facts and chapter rail', () => {
    render(<LandingPage />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Your career deserves a command center.',
    );
    expect(screen.getByRole('link', { name: /view on github/i })).toHaveAttribute(
      'href',
      'https://github.com/chintu79/careeros',
    );

    const rail = screen.getByRole('navigation', { name: 'Story chapters' });
    expect(within(rail).getByRole('link', { name: /discover/i })).toHaveAttribute(
      'href',
      '#discover',
    );

    for (const id of [
      'problem',
      'workspace',
      'discover',
      'track',
      'resume',
      'interviews',
      'insights',
      'open-source',
    ]) {
      expect(document.getElementById(id)).toBeInTheDocument();
    }
  });

  it('opens and closes the mobile menu', () => {
    render(<LandingPage />);

    const toggle = screen.getByRole('button', { name: 'Open menu' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );

    const mobileNav = screen.getByRole('navigation', { name: 'Mobile' });
    expect(within(mobileNav).getByRole('link', { name: /product/i })).toHaveAttribute(
      'href',
      '#workspace',
    );

    fireEvent.click(within(mobileNav).getByRole('link', { name: /product/i }));
    expect(screen.queryByRole('navigation', { name: 'Mobile' })).not.toBeInTheDocument();
  });

  it('filters the discovery demo and toggles a saved opportunity', () => {
    const { container } = render(<LandingPage />);

    const demo = container.querySelector('.demo') as HTMLElement;
    const scope = within(demo);

    fireEvent.click(scope.getByRole('button', { name: 'Remote' }));
    expect(scope.getByRole('button', { name: /Backend Engineering Intern/i })).toBeInTheDocument();

    fireEvent.click(scope.getByRole('button', { name: /Developer Experience Intern/i }));
    expect(scope.getByRole('button', { name: 'Save opportunity' })).toBeInTheDocument();
    fireEvent.click(scope.getByRole('button', { name: 'Save opportunity' }));
    expect(scope.getByRole('button', { name: 'Saved' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('moves a card through the application board', () => {
    render(<LandingPage />);

    expect(screen.getByText(/Linear · Assessment/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Move Linear forward a stage' }));
    expect(screen.getByText(/Linear · Interview/)).toBeInTheDocument();
    expect(screen.getByText(/Stage 4 of 5/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Move Linear back a stage' }));
    expect(screen.getByText(/Linear · Assessment/)).toBeInTheDocument();
  });

  it('unchecks a resume bullet and toggles the tailored variant', () => {
    const { container } = render(<LandingPage />);

    const sheet = container.querySelector('.resume__sheet') as HTMLElement;
    expect(sheet).toHaveTextContent('400 ms lock wait');

    fireEvent.click(
      screen.getByRole('checkbox', { name: /p99-latency tracing for the ingest path/i }),
    );
    expect(sheet).not.toHaveTextContent('400 ms lock wait');

    fireEvent.click(screen.getByRole('button', { name: /Tailor to Linear/i }));
    expect(sheet).toHaveTextContent(/Linear/);
    expect(screen.getByRole('button', { name: /Reset to master/i })).toBeInTheDocument();
  });

  it('tracks interview preparation progress', () => {
    render(<LandingPage />);

    expect(screen.getByText('0 of 3 ready')).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: /token-bucket math out loud/i }),
    );
    expect(screen.getByText('1 of 3 ready')).toBeInTheDocument();
  });

  it('renders every FAQ item', () => {
    const { container } = render(<LandingPage />);

    const items = container.querySelectorAll('details');
    expect(items.length).toBe(6);
    expect(screen.getByText('Is CareerOS free and open source?')).toBeInTheDocument();
  });
});
