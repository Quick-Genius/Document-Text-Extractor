import { useState, useMemo } from 'react';
import { useReactTable, getCoreRowModel, flexRender, getSortedRowModel } from '@tanstack/react-table';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import { useDocuments } from '../../hooks/useDocuments';
import { StatusFilter } from './StatusFilter';
import { SearchBar } from './SearchBar';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { format } from 'date-fns';
import { ActionButtons } from './ActionButtons';
import { cancelDocument, retryDocument, deleteDocument } from '../../services/documentService';
import { useApi } from '../../hooks/useApi';

interface Document {
  id: string;
  originalName: string;
  status: string;
  uploadedAt: string;
  fileSize: number;
  filePath?: string;
  job?: {
    retryCount?: number;
    maxRetries?: number;
  };
  queuePosition?: number;
}

export function DocumentList() {
  const api = useApi();
  const [filters, setFilters] = useState<{
    status: string[];
    search: string;
    sort_by: string;
    order: string;
    page: number;
    limit: number;
  }>({ status: [], search: '', sort_by: 'uploadedAt', order: 'desc', page: 1, limit: 10 });
  const [sorting, setSorting] = useState<SortingState>([]);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const navigate = useNavigate();
  
  const { data, isLoading, error, refetch } = useDocuments(filters);

  const handleCancel = async (documentId: string) => {
    try {
      await cancelDocument(api, documentId);
      setNotification({ type: 'success', message: 'Document cancelled successfully' });
      refetch();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.response?.data?.detail || 'Failed to cancel document' });
      throw err;
    }
  };

  const handleRetry = async (documentId: string) => {
    try {
      await retryDocument(api, documentId);
      setNotification({ type: 'success', message: 'Document queued for retry' });
      refetch();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.response?.data?.detail || 'Failed to retry document' });
      throw err;
    }
  };

  const handleDelete = async (documentId: string, permanent: boolean) => {
    try {
      await deleteDocument(api, documentId, permanent);
      setNotification({ type: 'success', message: permanent ? 'Record removed successfully' : 'Document deleted successfully' });
      refetch();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.response?.data?.detail || 'Failed to act on document' });
      throw err;
    }
  };

  const columns = useMemo<ColumnDef<Document>[]>(() => [
    {
      accessorKey: 'originalName',
      header: ({ column }) => (
        <button onClick={() => column.toggleSorting()} className="flex items-center gap-2 hover:text-primary transition-colors text-xs font-bold uppercase tracking-widest text-on-surface-variant group">
          Document Name <span className="material-symbols-outlined text-sm opacity-0 group-hover:opacity-100 transition-opacity">swap_vert</span>
        </button>
      ),
      cell: ({ row }) => {
        const status = row.original.status;
        const iconColorMap: Record<string, string> = {
          'PENDING': 'text-slate-500 bg-slate-100',
          'QUEUED': 'text-slate-500 bg-slate-100',
          'PROCESSING': 'text-blue-600 bg-blue-100 ring-2 ring-blue-100',
          'COMPLETED': 'text-primary-container bg-primary-fixed/30',
          'FAILED': 'text-error bg-error-container',
        };
        const iconMap: Record<string, string> = {
          'PENDING': 'pending',
          'QUEUED': 'pending',
          'PROCESSING': 'sync',
          'COMPLETED': 'description',
          'FAILED': 'report',
        };

        return (
          <div className="flex items-center gap-3">
            <span className={`material-symbols-outlined p-2 rounded-md ${iconColorMap[status] || iconColorMap.QUEUED}`}>
              {iconMap[status] || iconMap.QUEUED}
            </span>
            <div className="flex flex-col">
              <span className="font-semibold text-on-surface truncate max-w-[200px]">{row.original.originalName}</span>
              <span className="text-xs text-on-surface-variant">{(row.original.fileSize / 1024 / 1024).toFixed(2)} MB</span>
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: 'status',
      header: () => <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">Status</span>,
      cell: ({ row }) => {
        const status = row.getValue('status') as string;
        const colorMap: Record<string, string> = {
          'PENDING': 'bg-slate-100 text-slate-600',
          'QUEUED': 'bg-slate-100 text-slate-600',
          'PROCESSING': 'bg-blue-100 text-blue-700 shadow-[0_0_12px_rgba(59,130,246,0.5)]',
          'COMPLETED': 'bg-emerald-100 text-emerald-700',
          'FAILED': 'bg-error-container text-error',
        };
        const dotMap: Record<string, string> = {
          'PENDING': 'bg-slate-400',
          'QUEUED': 'bg-slate-400',
          'PROCESSING': 'bg-blue-500 animate-pulse',
          'COMPLETED': 'bg-emerald-500',
          'FAILED': 'bg-error',
        };
        return (
          <div className="flex flex-col items-start gap-1">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-tight transition-all duration-300 ${colorMap[status] || colorMap.QUEUED}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${dotMap[status] || dotMap.QUEUED}`}></span>
              {status}
            </span>
            {status === 'PENDING' && row.original.queuePosition !== undefined && (
              <span className="text-[10px] text-slate-500 font-semibold tracking-wider ml-1">
                WAITLIST: #{row.original.queuePosition}
              </span>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: 'uploadedAt',
      header: ({ column }) => (
        <button onClick={() => column.toggleSorting()} className="flex items-center gap-2 hover:text-primary transition-colors text-xs font-bold uppercase tracking-widest text-on-surface-variant group">
          Uploaded At <span className="material-symbols-outlined text-sm opacity-0 group-hover:opacity-100 transition-opacity">swap_vert</span>
        </button>
      ),
      cell: ({ row }) => (
        <div className="flex flex-col text-sm text-on-surface">
          <span className="font-medium">{format(new Date(row.getValue('uploadedAt') as string), 'MMM dd, yyyy')}</span>
          <span className="text-xs text-on-surface-variant">{format(new Date(row.getValue('uploadedAt') as string), 'HH:mm')}</span>
        </div>
      ),
    },
    {
      id: 'actions',
      header: () => <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant block text-right">Actions</span>,
      cell: ({ row }) => (
        <div className="flex items-center justify-end gap-3" onClick={(e) => e.stopPropagation()}>
          <ActionButtons
            document={row.original}
            onCancel={handleCancel}
            onRetry={handleRetry}
            onDelete={handleDelete}
          />
        </div>
      ),
    }
  ], []);

  const table = useReactTable({
    data: data?.documents || [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (isLoading) return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <span className="material-symbols-outlined text-4xl text-primary animate-spin" style={{ fontVariationSettings: "'FILL' 0" }}>sync</span>
      <span className="text-on-surface-variant font-medium">Fetching your documents...</span>
    </div>
  );

  if (error) return (
    <div className="p-8 rounded-3xl bg-error-container text-center max-w-lg mx-auto mt-12 mb-12 border border-error/20">
      <div className="w-16 h-16 bg-error/10 border border-error/20 rounded-full flex items-center justify-center mx-auto mb-4">
        <span className="material-symbols-outlined text-4xl text-error">report</span>
      </div>
      <h3 className="text-xl font-bold text-on-error-container mb-2">Sync Failed</h3>
      <p className="text-on-error-container/80">We couldn't load your documents. Please refresh the page or try again later.</p>
    </div>
  );

  return (
    <div className="flex flex-col w-full">
      {notification && (
        <div className={`p-4 mb-4 rounded-lg ${notification.type === 'success' ? 'bg-emerald-100 text-emerald-700' : 'bg-error-container text-error'}`}>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined">{notification.type === 'success' ? 'check_circle' : 'error'}</span>
            <span className="font-medium">{notification.message}</span>
            <button onClick={() => setNotification(null)} className="ml-auto">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>
      )}
      <div className="p-6 border-b border-outline-variant/10 flex flex-col md:flex-row justify-between gap-4 bg-surface-container-lowest/50">
        <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0">
          <StatusFilter onChange={status => setFilters({ ...filters, status: status.join(',') as any })} />
        </div>
        <div className="relative">
          <SearchBar onSearch={search => setFilters({ ...filters, search })} />
        </div>
        <div className="hidden text-sm text-on-surface-variant font-medium self-center">
          Showing {data?.documents?.length || 0} of {data?.pagination?.total || 0}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id} className="bg-surface-container-low/30 border-b border-outline-variant/10">
                {headerGroup.headers.map(header => (
                  <th key={header.id} className="px-8 py-4">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-outline-variant/5">
            {table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map((row, idx) => (
                <motion.tr 
                  key={row.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  onClick={() => navigate(`/documents/${row.original.id}`)}
                  className="hover:bg-surface-container-high/40 transition-colors group cursor-pointer"
                >
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-8 py-5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </motion.tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="px-8 py-20 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-20 h-20 bg-surface-container rounded-full flex items-center justify-center mb-2">
                       <span className="material-symbols-outlined text-4xl text-on-surface-variant">search_off</span>
                    </div>
                    <h4 className="text-xl font-bold text-on-surface">No documents found</h4>
                    <p className="text-sm text-on-surface-variant max-w-sm mx-auto">Try adjusting your filters or upload a new file to start the extraction pipeline.</p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {data?.pagination && data.pagination.pages > 1 && (
        <div className="p-6 border-t border-outline-variant/10 flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm text-on-surface-variant font-medium">
            Showing page {filters.page} of {data.pagination.pages}
          </span>
          <div className="flex items-center gap-2">
            {Array.from({ length: Math.min(5, data.pagination.pages) }).map((_, i) => {
              const pageNum = i + 1;
              const isActive = filters.page === pageNum;
              return (
                <button
                  key={i}
                  onClick={() => setFilters({ ...filters, page: pageNum })}
                  className={`w-10 h-10 rounded-md font-bold transition-all flex items-center justify-center
                    ${isActive 
                      ? 'bg-primary-container text-on-primary-container' 
                      : 'border border-outline-variant/20 text-on-surface-variant hover:bg-surface-container-low'}`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
