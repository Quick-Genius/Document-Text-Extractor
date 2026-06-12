import { useState } from 'react';
import { Filter } from 'lucide-react';

interface StatusFilterProps {
  onChange: (status: string[]) => void;
}

const STATUS_OPTIONS = [
  { label: 'Queued', value: 'QUEUED' },
  { label: 'Processing', value: 'PROCESSING' },
  { label: 'Completed', value: 'COMPLETED' },
  { label: 'Failed', value: 'FAILED' },
];

export function StatusFilter({ onChange }: StatusFilterProps) {
  const [selected, setSelected] = useState<string[]>([]);

  const handleToggle = (status: string) => {
    const newSelected = selected.includes(status)
      ? selected.filter(s => s !== status)
      : [...selected, status];
    setSelected(newSelected);
    onChange(newSelected);
  };

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-2 sm:pb-0 no-scrollbar">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900/60 border border-slate-800 rounded-lg text-xs font-bold text-slate-400 uppercase">
        <Filter className="w-3.5 h-3.5" /> Filter
      </div>
      {STATUS_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => handleToggle(opt.value)}
          type="button"
          className={`whitespace-nowrap px-4 py-1.5 rounded-lg text-sm font-semibold transition-all border
            ${selected.includes(opt.value)
              ? 'bg-indigo-600 border-indigo-600 text-white shadow-md shadow-indigo-500/10'
              : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:border-indigo-500/30 hover:bg-indigo-500/5'}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
