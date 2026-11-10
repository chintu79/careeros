import React from 'react';
import { Keyboard, X } from 'lucide-react';
import { Modal } from '../ui/Modal';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  const shortcutGroups = [
    {
      title: 'Global Navigation & Commands',
      items: [
        { keys: ['⌘', 'J'], label: 'Open Global AI Command Center' },
        { keys: ['⌘', 'K'], label: 'Open Command Palette' },
        { keys: ['['], label: 'Toggle sidebar collapse' },
        { keys: ['?'], label: 'Open Keyboard Shortcuts' },
        { keys: ['Esc'], label: 'Close active modal / dialog' },
      ],
    },
    {
      title: 'Section Jumping (Press sequentially)',
      items: [
        { keys: ['G', 'O'], label: 'Go to Overview' },
        { keys: ['G', 'D'], label: 'Go to Discover' },
        { keys: ['G', 'A'], label: 'Go to Applications' },
        { keys: ['G', 'R'], label: 'Go to Resume Studio' },
        { keys: ['G', 'I'], label: 'Go to Interviews' },
        { keys: ['G', 'N'], label: 'Go to Career Insights' },
        { keys: ['G', 'C'], label: 'Go to AI Assistant' },
        { keys: ['G', 'P'], label: 'Go to My Profile' },
        { keys: ['G', 'S'], label: 'Go to Settings' },
      ],
    },
    {
      title: 'Quick Pipeline Actions',
      items: [
        { keys: ['⌘', 'S'], label: 'Sync all job sources' },
        { keys: ['⌘', 'I'], label: 'Import new job posting' },
      ],
    },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center space-x-2">
          <Keyboard className="w-5 h-5 text-emerald-400" aria-hidden="true" />
          <span>Keyboard Shortcuts</span>
        </div>
      }
      subtitle="Navigate and control CareerOS at full keyboard speed."
      size="md"
    >
      <div className="p-5 space-y-5">
        {shortcutGroups.map((group, gIdx) => (
          <div key={gIdx} className="space-y-2">
            <h4 className="text-[11px] font-bold  text-slate-400">
              {group.title}
            </h4>
            <ul className="rounded-xl border border-slate-800 divide-y divide-slate-800/60 bg-slate-950/60 overflow-hidden" role="list">
              {group.items.map((item, idx) => (
                <li
                  key={idx}
                  className="px-3.5 py-2.5 flex items-center justify-between text-xs"
                >
                  <span className="text-slate-300 font-medium">{item.label}</span>
                  <div className="flex items-center space-x-1">
                    {item.keys.map((k, kIdx) => (
                      <kbd
                        key={kIdx}
                        className="px-2 py-0.5 rounded font-mono text-[11px] font-bold bg-slate-900 border border-slate-700 text-slate-300"
                      >
                        {k}
                      </kbd>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Modal>
  );
};
