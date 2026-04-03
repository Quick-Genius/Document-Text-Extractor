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
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs font-bold text-gray-500 uppercase">
        <Filter className="w-3.5 h-3.5" /> Filter
      </div>
      {STATUS_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => handleToggle(opt.value)}
          type="button"
          className={`whitespace-nowrap px-4 py-1.5 rounded-lg text-sm font-semibold transition-all border
            ${selected.includes(opt.value)
              ? 'bg-blue-600 border-blue-600 text-white shadow-md shadow-blue-100'
              : 'bg-white border-gray-200 text-gray-600 hover:border-blue-400 hover:bg-blue-50/10'}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
