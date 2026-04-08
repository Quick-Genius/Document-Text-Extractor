import { useDocument } from '../../hooks/useDocuments';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateProcessedData, finalizeDocument, deleteDocument, retryDocument } from '../../services/documentService';
import { EditForm } from './EditForm';
import { ProgressTracker } from './ProgressTracker';
import { useApi } from '../../hooks/useApi';
import { Link, useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { motion } from 'framer-motion';
import { useState } from 'react';
import { exportToJson } from '../../services/exportService';
import { useAuth } from '@clerk/clerk-react';

interface DocumentDetailProps {
  documentId: string;
}

export function DocumentDetail({ documentId }: DocumentDetailProps) {
  const navigate = useNavigate();
  const api = useApi();
  const queryClient = useQueryClient();
  const { getToken } = useAuth();
  const { data: document, isLoading, error } = useDocument(documentId);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDownload = async () => {
    const token = await getToken();
    const url = `/api/v1/documents/${documentId}/preview?download=true&token=${token}`;
    const a = window.document.createElement('a');
    a.href = url;
    a.download = document?.originalName || 'document';
    a.click();
  };

  const updateMutation = useMutation({
    mutationFn: (data: any) => updateProcessedData(api, documentId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', documentId] });
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: () => finalizeDocument(api, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', documentId] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => retryDocument(api, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', documentId] });
    },
  });

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this document? This action cannot be undone.')) return;
    setIsDeleting(true);
    try {
      await deleteDocument(api, documentId);
      navigate('/dashboard');
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading) return (
    <div className="flex flex-col items-center justify-center py-32 gap-4">
      <span className="material-symbols-outlined text-4xl text-primary animate-spin" style={{ fontVariationSettings: "'FILL' 0" }}>sync</span>
      <span className="text-on-surface-variant font-medium text-lg">Analyzing document data...</span>
    </div>
  );

  if (error || !document) return (
    <div className="max-w-xl mx-auto py-20 text-center">
      <div className="w-20 h-20 bg-error-container border border-error/20 rounded-full flex items-center justify-center mx-auto mb-6">
        <span className="material-symbols-outlined text-4xl text-error">report</span>
      </div>
      <h2 className="text-2xl font-bold text-on-surface mb-2">Document Not Found</h2>
      <p className="text-on-surface-variant mb-8">The document you're looking for doesn't exist or you don't have permission to view it.</p>
      <Link to="/dashboard" className="inline-flex items-center gap-2 text-primary font-bold hover:underline">
        <span className="material-symbols-outlined">arrow_back</span> Back to Dashboard
      </Link>
    </div>
  );

  const isCompleted = document.status === 'COMPLETED';
  const isFinalized = document.processedData?.isFinalized;

  const iconColorMap: Record<string, string> = {
    'QUEUED': 'bg-slate-100 text-slate-500',
    'PROCESSING': 'bg-blue-100 text-blue-600',
    'COMPLETED': 'bg-primary-fixed text-primary',
    'FAILED': 'bg-error-container text-error',
  };
  const iconMap: Record<string, string> = {
    'QUEUED': 'pending',
    'PROCESSING': 'sync',
    'COMPLETED': 'description',
    'FAILED': 'report',
  };
  const dotMap: Record<string, string> = {
    'QUEUED': 'bg-slate-400',
    'PROCESSING': 'bg-blue-500 animate-pulse',
    'COMPLETED': 'bg-emerald-500',
    'FAILED': 'bg-error',
  };

  return (
    <div className="space-y-8">
      {/* Back Navigation */}
      <nav>
        <Link to="/dashboard" className="inline-flex items-center gap-2 text-on-surface-variant hover:text-primary transition-all duration-200 group">
          <span className="material-symbols-outlined group-hover:-translate-x-1 transition-transform">arrow_back</span>
          <span className="font-semibold text-sm">Back to Dashboard</span>
        </Link>
      </nav>

      {/* Document Header Section */}
      <section className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-6 border-b border-outline-variant/20">
        <div className="flex items-center gap-5">
          <div className={`w-16 h-16 flex items-center justify-center rounded-lg shadow-sm ${iconColorMap[document.status] || iconColorMap.QUEUED}`}>
            <span className={`material-symbols-outlined text-3xl ${document.status === 'PROCESSING' ? 'animate-spin' : ''}`}>
              {iconMap[document.status] || iconMap.QUEUED}
            </span>
          </div>
          <div className="space-y-1">
            <h1 className="text-3xl font-black tracking-tight text-on-surface break-all">{document.originalName}</h1>
            <div className="flex flex-wrap items-center gap-4 text-sm text-on-surface-variant">
              <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-sm">calendar_today</span> {format(new Date(document.uploadedAt), 'PPP')}</span>
              <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-sm">file_present</span> {document.fileType || 'PDF'}</span>
              <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-sm">database</span> {(document.fileSize / 1024 / 1024).toFixed(2)} MB</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {document.status === 'FAILED' && (
            <button
              onClick={() => retryMutation.mutate()}
              disabled={retryMutation.isPending}
              className="px-5 py-2.5 rounded-md font-semibold text-sm bg-primary text-on-primary hover:bg-primary/90 transition-all active:scale-95 disabled:opacity-50 flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-sm">refresh</span>
              {retryMutation.isPending ? 'Retrying...' : 'Restart Processing'}
            </button>
          )}
          <button
            onClick={handleDownload}
            className="px-5 py-2.5 rounded-md font-semibold text-sm bg-surface-container-lowest border border-outline-variant/20 hover:bg-surface-container-low transition-all active:scale-95 flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-sm">download</span>
            Download
          </button>
          <button
            onClick={() => exportToJson(api, documentId)}
            disabled={!isCompleted}
            className="px-5 py-2.5 rounded-md font-semibold text-sm bg-surface-container-lowest border border-outline-variant/20 hover:bg-surface-container-low transition-all active:scale-95 disabled:opacity-50"
          >
            Export JSON
          </button>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="px-5 py-2.5 rounded-md font-semibold text-sm bg-error-container text-on-error-container hover:bg-error/10 transition-all active:scale-95 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </section>

      {/* Layout Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left Column (Main Content) */}
        <div className="lg:col-span-2 space-y-8">
          {!isCompleted && document.job && (
            <article className="bg-primary-container text-on-primary rounded-lg p-8 shadow-xl shadow-indigo-200/50 relative overflow-hidden">
              <div className="relative z-10">
                <div className="flex justify-between items-center mb-10">
                  <h2 className="text-xl font-bold">Processing Pipeline</h2>
                  <span className="px-3 py-1 bg-white/20 rounded-full text-xs font-bold tracking-widest uppercase">Live Extraction</span>
                </div>
                <ProgressTracker job={document.job} />
              </div>
            </article>
          )}

          {isCompleted && (
            <motion.article 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card rounded-lg p-8 border border-outline-variant/10 shadow-sm space-y-8"
            >
              <div className="flex justify-between items-center">
                <div className="space-y-1">
                  <h2 className="text-2xl font-bold tracking-tight text-on-surface">Extracted Intelligence</h2>
                  <p className="text-sm text-on-surface-variant">Verify and refine the AI-generated metadata</p>
                </div>
                {isFinalized && (
                  <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200">
                    <span className="material-symbols-outlined text-[10px] bg-emerald-500 text-white rounded-full">check</span>
                    <span className="text-[10px] font-bold tracking-widest uppercase">Finalized</span>
                  </div>
                )}
              </div>
              
              {document.processedData && (
                <EditForm 
                  data={document.processedData} 
                  isReadOnly={isFinalized}
                  onSave={(data) => updateMutation.mutate(data)} 
                  onFinalize={() => finalizeMutation.mutate()}
                />
              )}
            </motion.article>
          )}
        </div>

        {/* Right Column (Sidebar) */}
        <aside className="space-y-6">
          {/* Pipeline Metadata Card */}
          <div className="bg-surface-container-low rounded-lg p-6 space-y-6 shadow-sm border border-outline-variant/10">
            <h3 className="font-bold text-lg text-on-surface tracking-tight">Pipeline Metadata</h3>
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-[10px] font-bold text-on-surface-variant tracking-widest uppercase">Document ID</p>
                <p className="font-mono text-xs bg-white p-2 rounded border border-outline-variant/10 text-primary truncate" title={documentId}>{documentId}</p>
              </div>
              <div className="space-y-1">
                <p className="text-[10px] font-bold text-on-surface-variant tracking-widest uppercase">Status</p>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tracking-tight uppercase 
                  ${isCompleted ? 'bg-emerald-100 text-emerald-700' : 
                    document.status === 'FAILED' ? 'bg-error-container text-error' : 
                    document.status === 'QUEUED' ? 'bg-slate-100 text-slate-600' : 'bg-primary-fixed text-primary'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${dotMap[document.status] || dotMap.QUEUED}`}></span>
                  {document.status}
                </span>
              </div>
              
              <div className="pt-4 space-y-3 border-t border-outline-variant/20">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-on-surface-variant">Worker Tier</span>
                  <span className="font-semibold text-on-surface">Standard</span>
                </div>
                {document.job?.createdAt && (
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-on-surface-variant">Started</span>
                    <span className="font-semibold text-on-surface">{format(new Date(document.job.createdAt), 'HH:mm:ss')}</span>
                  </div>
                )}
                <div className="flex justify-between items-center text-sm">
                  <span className="text-on-surface-variant">Parser Engine</span>
                  <span className="font-semibold text-on-surface">Gemini 1.5</span>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
