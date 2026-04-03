import { DocumentList } from '../components/dashboard/DocumentList';
import { exportToCsv } from '../services/exportService';
import { getDashboardStats } from '../services/documentService';
import { Link } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import { useState, useEffect } from 'react';

interface StatsData {
  active_jobs: number;
  storage_used_mb: number;
  success_rate: number;
}

export function DashboardPage() {
  const api = useApi();
  const [isExporting, setIsExporting] = useState(false);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setStatsLoading(true);
        const data = await getDashboardStats(api);
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch dashboard stats:', error);
      } finally {
        setStatsLoading(false);
      }
    };

    fetchStats();
  }, [api]);

  const statCards = [
    {
      label: 'Active Jobs',
      value: stats?.active_jobs.toString() || '—',
      icon: 'rocket_launch',
      gradient: 'from-indigo-600 to-blue-500',
      badgeBg: 'bg-emerald-400/20',
      badgeText: 'text-emerald-100',
    },
    {
      label: 'Storage Used',
      value: stats ? `${(stats.storage_used_mb / 1024).toFixed(2)} GB` : '—',
      icon: 'database',
      gradient: 'from-violet-600 to-purple-500',
      badgeBg: '',
      badgeText: '',
    },
    {
      label: 'Success Rate',
      value: stats ? `${stats.success_rate.toFixed(1)}%` : '—',
      icon: 'check_circle',
      gradient: 'from-emerald-600 to-teal-500',
      badgeBg: '',
      badgeText: '',
    },
  ];

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportToCsv(api);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <>
      <main className="pt-32 pb-20 px-8 max-w-7xl mx-auto flex-grow">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-12">
          <div>
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-error-container text-on-error-container text-xs font-bold tracking-widest uppercase mb-4">
              <span className="w-2 h-2 rounded-full bg-error animate-pulse"></span>
              Live Pipeline
            </span>
            <h1 className="text-5xl font-extrabold tracking-tight text-on-surface mb-2">Documents Dashboard</h1>
            <p className="text-on-surface-variant text-lg">Monitor real-time document processing and extraction status.</p>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="glass-card border border-outline-variant/20 px-6 py-3 rounded-lg text-on-surface font-semibold flex items-center gap-2 hover:bg-surface-container-low transition-all active:scale-95 shadow-sm disabled:opacity-50"
            >
              <span className={`material-symbols-outlined text-lg ${isExporting ? 'animate-bounce' : ''}`}>download</span>
              {isExporting ? 'Exporting...' : 'Export CSV'}
            </button>
            <Link
              to="/"
              className="signature-gradient px-8 py-3 rounded-lg text-on-primary font-bold flex items-center gap-2 hover:opacity-90 transition-all active:scale-95 shadow-lg shadow-indigo-200/50"
            >
              <span className="material-symbols-outlined text-lg">add_circle</span>
              New Upload
            </Link>
          </div>
        </div>

        {/* Stat Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {statCards.map((card, idx) => (
            <div key={card.label} className={`relative overflow-hidden rounded-lg p-8 bg-gradient-to-br ${card.gradient} text-white shadow-xl hover:-translate-y-1 transition-transform`}>
              <div className="absolute -right-4 -top-4 w-32 h-32 bg-white/10 rounded-full blur-3xl"></div>
              <div className="flex justify-between items-start mb-6 align-top">
                <span className="material-symbols-outlined bg-white/20 p-3 rounded-md shadow-sm">{card.icon}</span>
                {card.change && (
                  <span className={`${card.badgeBg} ${card.badgeText} text-xs font-bold px-2 py-1 rounded-full`}>
                    {card.change}
                  </span>
                )}
              </div>
              <div className="text-sm font-semibold uppercase tracking-wider opacity-90 mb-1">{card.label}</div>
              <div className="text-4xl font-extrabold tracking-tight">{card.value}</div>
            </div>
          ))}
        </div>

        {/* Document Table Container */}
        <div className="glass-card rounded-lg border border-outline-variant/10 shadow-[0_20px_50px_-12px_rgba(79,70,229,0.08)] overflow-hidden">
          <DocumentList />
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-outline-variant/20 bg-surface-container-low mt-auto">
        <div className="flex flex-col md:flex-row justify-between items-center px-8 py-12 max-w-7xl mx-auto gap-6">
          <div className="flex flex-col gap-2 text-center md:text-left">
            <span className="font-bold text-on-surface text-lg tracking-tight">DocFlow AI</span>
            <p className="font-['Inter'] text-sm text-on-surface-variant">© 2024 DocFlow AI. Built for Sophisticated Air.</p>
          </div>
          <div className="flex flex-wrap justify-center gap-8">
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all text-sm">Terms</a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all text-sm">Privacy</a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all text-sm">Documentation</a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all text-sm">Support</a>
          </div>
        </div>
      </footer>
    </>
  );
}
