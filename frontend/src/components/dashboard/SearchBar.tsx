import { useState, useEffect } from 'react';
import { Search, X } from 'lucide-react';

interface SearchBarProps {
  onSearch: (query: string) => void;
}

export function SearchBar({ onSearch }: SearchBarProps) {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(query);
    }, 400);
    return () => clearTimeout(timer);
  }, [query, onSearch]);

  return (
    <div className="relative group flex-1 max-w-sm">
      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
        <Search className="h-4 w-4 text-slate-500 group-focus-within:text-indigo-450 transition-colors" />
      </div>
      <input
        type="text"
        className="block w-full pl-10 pr-10 py-2.5 bg-slate-900/60 border border-slate-800 rounded-xl leading-5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:bg-slate-900 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all sm:text-sm"
        placeholder="Search documents..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {query && (
        <button
          onClick={() => setQuery('')}
          className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-500 hover:text-slate-300 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
