import { useState } from 'react';

interface Job {
  retryCount?: number;
  maxRetries?: number;
}

interface Document {
  id: string;
  status: string;
  job?: Job;
}

interface ActionButtonsProps {
  document: Document;
  onCancel: (id: string) => Promise<void>;
  onRetry: (id: string) => Promise<void>;
}

export function ActionButtons({ document, onCancel, onRetry }: ActionButtonsProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = async () => {
    setLoading(true);
    setError(null);
    try {
      await onCancel(document.id);
    } catch (err: any) {
      setError(err.message || 'Failed to cancel document');
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    setLoading(true);
    setError(null);
    try {
      await onRetry(document.id);
    } catch (err: any) {
      setError(err.message || 'Failed to retry document');
    } finally {
      setLoading(false);
    }
  };

  // Show stop button for PROCESSING or QUEUED
  if (document.status === 'PROCESSING' || document.status === 'QUEUED') {
    return (
      <div className="flex flex-col items-end gap-1">
        <button
          onClick={handleCancel}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-error/10 text-error hover:bg-error/20 transition-colors disabled:opacity-50 text-sm font-medium"
        >
          <span className="material-symbols-outlined text-base">stop_circle</span>
          {loading ? 'Cancelling...' : 'Stop'}
        </button>
        {error && <span className="text-xs text-error">{error}</span>}
      </div>
    );
  }

  // Show retry button for FAILED
  if (document.status === 'FAILED') {
    const retryCount = document.job?.retryCount || 0;
    const maxRetries = document.job?.maxRetries || 3;
    const canRetry = retryCount < maxRetries;

    if (!canRetry) {
      return (
        <div className="text-xs text-on-surface-variant text-right max-w-[120px]">
          Maximum retry attempts reached. Please re-upload.
        </div>
      );
    }

    return (
      <div className="flex flex-col items-end gap-1">
        <button
          onClick={handleRetry}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50 text-sm font-medium"
        >
          <span className="material-symbols-outlined text-base">refresh</span>
          {loading ? 'Retrying...' : 'Retry'}
        </button>
        {error && <span className="text-xs text-error">{error}</span>}
      </div>
    );
  }

  return null;
}
