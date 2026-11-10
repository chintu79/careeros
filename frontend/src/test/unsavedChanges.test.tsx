import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import {
  UnsavedChangesProvider,
  useNavigationGuard,
  useUnsavedChangesGuard,
} from '../context/unsavedChanges';

const NavProbe: React.FC<{ apply: () => void }> = ({ apply }) => {
  const guardedNav = useNavigationGuard();
  return <button onClick={() => guardedNav(apply)}>Navigate</button>;
};

const EditorProbe: React.FC<{ dirty: boolean }> = ({ dirty }) => {
  useUnsavedChangesGuard('probe:editor', dirty, 'Probe edits are not saved');
  return null;
};

function renderWith(dirty: boolean, apply: () => void) {
  return render(
    <UnsavedChangesProvider>
      <EditorProbe dirty={dirty} />
      <NavProbe apply={apply} />
    </UnsavedChangesProvider>
  );
}

describe('UnsavedChangesProvider navigation guard', () => {
  it('applies navigation immediately when no editor is dirty', () => {
    const apply = vi.fn();
    renderWith(false, apply);
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    expect(apply).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('blocks navigation while dirty and "Stay" keeps editing', () => {
    const apply = vi.fn();
    renderWith(true, apply);
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    expect(apply).not.toHaveBeenCalled();
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(screen.getByText(/Probe edits are not saved/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Stay and keep editing/ }));
    expect(apply).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('discards and navigates when the discard action is confirmed', () => {
    const apply = vi.fn();
    renderWith(true, apply);
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    fireEvent.click(screen.getByRole('button', { name: /Discard changes and leave/ }));
    expect(apply).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('releases pending navigation once the editor is saved (dirty -> clean)', () => {
    const apply = vi.fn();
    const { rerender } = render(
      <UnsavedChangesProvider>
        <EditorProbe dirty={true} />
        <NavProbe apply={apply} />
      </UnsavedChangesProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();

    // Simulate a successful save: editor flips to clean; pending navigation is released
    rerender(
      <UnsavedChangesProvider>
        <EditorProbe dirty={false} />
        <NavProbe apply={apply} />
      </UnsavedChangesProvider>
    );
    expect(apply).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });
});
