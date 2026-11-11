import { render, screen, fireEvent, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import LandingPage from '../landing/LandingPage';

afterEach(() => {
  document.title = '';
  delete document.documentElement.dataset.page;
});

describe('LandingPage', () => {
  it('renders the hero, primary actions and verifiable facts', () => {
    render(<LandingPage />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Your career deserves a command center.',
    );
    expect(screen.getByRole('link', { name: /view on github/i })).toHaveAttribute(
      'href',
      'https://github.com/chintu79/careeros',
    );
    expect(screen.getByText('Apache-2.0', { selector: '.l-hero__facts li' })).toBeInTheDocument();
    expect(document.title).toBe('CareerOS: your career deserves a command center');
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
    expect(within(mobileNav).getByRole('link', { name: /open source/i })).toHaveAttribute(
      'href',
      '#open-source',
    );

    fireEvent.click(within(mobileNav).getByRole('link', { name: /product/i }));
    expect(screen.queryByRole('navigation', { name: 'Mobile' })).not.toBeInTheDocument();
  });

  it('moves the walkthrough tabs with the arrow keys', () => {
    render(<LandingPage />);

    const discover = screen.getByRole('tab', { name: /discover/i });
    expect(discover).toHaveAttribute('aria-selected', 'true');

    fireEvent.keyDown(discover, { key: 'ArrowRight' });
    expect(screen.getByRole('tab', { name: /organize/i })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('tab', { name: /discover/i })).toHaveAttribute(
      'aria-selected',
      'false',
    );
    expect(screen.getByRole('heading', { name: 'Every application, one record.' })).toBeInTheDocument();
  });

  it('renders every FAQ item and keeps answers in the document', () => {
    const { container } = render(<LandingPage />);

    const items = container.querySelectorAll('details');
    expect(items).toHaveLength(6);
    expect(screen.getByText('Is CareerOS free and open source?')).toBeInTheDocument();
    expect(
      screen.getByText(/Discovery covers Greenhouse, Lever, Ashby, SmartRecruiters/),
    ).toBeInTheDocument();
  });
});
