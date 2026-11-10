import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Compass,
  CheckSquare,
  FileText,
  BookOpen,
  Sparkles,
  Bot,
  User,
  Layers,
  BarChart3,
  Building2,
  RotateCw,
  PlusCircle,
  HelpCircle,
  ArrowRight,
  CornerDownLeft,
  X,
  Settings
} from 'lucide-react';
import { TOKENS } from '../ui/DesignTokens';
import { saveActiveElement, restoreActiveElement } from '../../utils/focusTrap';

interface CommandItem {
  id: string;
  title: string;
  category: 'Navigation' | 'Actions';
  icon: React.ReactNode;
  shortcut?: string;
  onSelect: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (tab: string) => void;
  onSyncAll: () => Promise<void>;
  onOpenImport: () => void;
  onOpenShortcuts: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onSyncAll,
  onOpenImport,
  onOpenShortcuts,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const allItems: CommandItem[] = [
    // Navigation items (Workspace)
    {
      id: 'nav-overview',
      title: 'Go to Overview',
      category: 'Navigation',
      icon: <BarChart3 className="w-4 h-4 text-emerald-400" />,
      shortcut: 'G O',
      onSelect: () => { onNavigate('overview'); onClose(); }
    },
    {
      id: 'nav-discover',
      title: 'Go to Discover',
      category: 'Navigation',
      icon: <Compass className="w-4 h-4 text-teal-400" />,
      shortcut: 'G D',
      onSelect: () => { onNavigate('discover'); onClose(); }
    },
    {
      id: 'nav-tracker',
      title: 'Go to Applications',
      category: 'Navigation',
      icon: <CheckSquare className="w-4 h-4 text-blue-400" />,
      shortcut: 'G A',
      onSelect: () => { onNavigate('tracker'); onClose(); }
    },
    {
      id: 'nav-resumes',
      title: 'Go to Resume Studio',
      category: 'Navigation',
      icon: <FileText className="w-4 h-4 text-emerald-300" />,
      shortcut: 'G R',
      onSelect: () => { onNavigate('resumes'); onClose(); }
    },
    {
      id: 'nav-interviews',
      title: 'Go to Interviews',
      category: 'Navigation',
      icon: <BookOpen className="w-4 h-4 text-amber-400" />,
      shortcut: 'G I',
      onSelect: () => { onNavigate('interviews'); onClose(); }
    },
    // Navigation items (Intelligence)
    {
      id: 'nav-analytics',
      title: 'Go to Career Insights',
      category: 'Navigation',
      icon: <Sparkles className="w-4 h-4 text-emerald-400" />,
      shortcut: 'G N',
      onSelect: () => { onNavigate('analytics'); onClose(); }
    },
    {
      id: 'nav-chat',
      title: 'Go to AI Assistant',
      category: 'Navigation',
      icon: <Bot className="w-4 h-4 text-sky-400" />,
      shortcut: 'G C',
      onSelect: () => { onNavigate('chat'); onClose(); }
    },
    // Navigation items (Personal)
    {
      id: 'nav-profile',
      title: 'Go to My Profile',
      category: 'Navigation',
      icon: <User className="w-4 h-4 text-slate-300" />,
      shortcut: 'G P',
      onSelect: () => { onNavigate('profile'); onClose(); }
    },
    {
      id: 'nav-preferences',
      title: 'Go to Settings',
      category: 'Navigation',
      icon: <Settings className="w-4 h-4 text-slate-300" />,
      shortcut: 'G S',
      onSelect: () => { onNavigate('preferences'); onClose(); }
    },
    {
      id: 'nav-onboarding',
      title: 'Profile Onboarding & Readiness Activation',
      category: 'Navigation',
      icon: <Sparkles className="w-4 h-4 text-emerald-400" />,
      shortcut: 'G Z',
      onSelect: () => { onNavigate('onboarding'); onClose(); }
    },
    // Quick Actions
    {
      id: 'act-sync',
      title: 'Sync All Job Feeds & Portals',
      category: 'Actions',
      icon: <RotateCw className="w-4 h-4 text-emerald-400" />,
      shortcut: '⌘S',
      onSelect: () => { onSyncAll(); onClose(); }
    },
    {
      id: 'act-import',
      title: 'Import Job Posting via Paste / URL',
      category: 'Actions',
      icon: <PlusCircle className="w-4 h-4 text-teal-400" />,
      shortcut: '⌘I',
      onSelect: () => { onClose(); onOpenImport(); }
    },
    {
      id: 'act-shortcuts',
      title: 'Open Keyboard Shortcuts Cheatsheet',
      category: 'Actions',
      icon: <HelpCircle className="w-4 h-4 text-slate-400" />,
      shortcut: '?',
      onSelect: () => { onClose(); onOpenShortcuts(); }
    },
  ];

  const filteredItems = allItems.filter(item =>
    item.title.toLowerCase().includes(query.toLowerCase()) ||
    item.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Keyboard navigation & focus restoration inside palette
  useEffect(() => {
    if (!isOpen) return;

    saveActiveElement();
    setTimeout(() => inputRef.current?.focus(), 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % Math.max(1, filteredItems.length));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredItems[selectedIndex]) {
          filteredItems[selectedIndex].onSelect();
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      restoreActiveElement();
    };
  }, [isOpen, filteredItems, selectedIndex, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-xl rounded-xl bg-slate-900 border border-slate-800 overflow-hidden flex flex-col animate-zoom-in">
        {/* Search Input Bar */}
        <div className="p-3.5 border-b border-slate-800 flex items-center space-x-3 bg-slate-950/70">
          <Search className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-autocomplete="list"
            aria-controls="cmd-palette-options"
            aria-activedescendant={filteredItems[selectedIndex] ? `cmd-opt-${filteredItems[selectedIndex].id}` : undefined}
            aria-label="Type a command or search sections"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search sections..."
            className="w-full bg-transparent text-sm text-[var(--color-ink)] placeholder-slate-400 focus:outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="p-1 rounded text-slate-400 hover:text-[var(--color-ink)] focus-visible:ring-1 focus-visible:ring-emerald-500"
              aria-label="Clear search input"
            >
              <X className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          )}
          <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700" aria-hidden="true">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div
          ref={listRef}
          id="cmd-palette-options"
          role="listbox"
          aria-label="Commands and navigation shortcuts"
          className="max-h-80 overflow-y-auto p-2 space-y-1"
        >
          {filteredItems.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400">
              No matching commands or destinations found.
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const isSelected = idx === selectedIndex;

              return (
                <div
                  key={item.id}
                  id={`cmd-opt-${item.id}`}
                  role="option"
                  aria-selected={isSelected}
                  onClick={item.onSelect}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs cursor-pointer select-none transition ${
                    isSelected
                      ? 'bg-emerald-500/10 text-[var(--color-ink)] border border-emerald-500/25 ring-1 ring-emerald-500/20'
                      : 'text-slate-300 hover:bg-slate-800/60 border border-transparent'
                  }`}
                >
                  <div className="flex items-center space-x-3 truncate">
                    <span className="shrink-0" aria-hidden="true">{item.icon}</span>
                    <span className="truncate font-medium">{item.title}</span>
                  </div>

                  <div className="flex items-center space-x-2 shrink-0">
                    {item.shortcut && (
                      <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-950 border border-slate-700 text-slate-400" aria-hidden="true">
                        {item.shortcut}
                      </kbd>
                    )}
                    {isSelected && (
                      <CornerDownLeft className="w-3.5 h-3.5 text-emerald-400 animate-pulse" aria-hidden="true" />
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Navigation Hints */}
        <div className="px-4 py-2 border-t border-slate-800/80 bg-slate-950/60 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center space-x-3">
            <span className="flex items-center space-x-1">
              <kbd className="px-1 py-0.2 rounded font-mono bg-slate-900 border border-slate-700">↑↓</kbd>
              <span>to navigate</span>
            </span>
            <span className="flex items-center space-x-1">
              <kbd className="px-1 py-0.2 rounded font-mono bg-slate-900 border border-slate-700">↵</kbd>
              <span>to select</span>
            </span>
          </div>
          <span>CareerOS Command Suite</span>
        </div>
      </div>
    </div>
  );
};
