import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';

interface Job {
  retryCount?: number;
  maxRetries?: number;
}

interface Document {
  id: string;
  status: string;
  filePath?: string;
  job?: Job;
  queuePosition?: number;
}

interface ActionButtonsProps {
  document: Document;
  onCancel: (id: string) => Promise<void>;
  onRetry: (id: string) => Promise<void>;
  onDelete: (id: string, permanent: boolean) => Promise<void>;
}

export function ActionButtons({ document, onCancel, onRetry, onDelete }: ActionButtonsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [loadingAction, setLoadingAction] = useState<'stop' | 'retry' | 'delete' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();
  const [dropdownPos, setDropdownPos] = useState({ top: 0, right: 0 });

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const isOutsideDropdown = dropdownRef.current && !dropdownRef.current.contains(event.target as Node);
      const isOutsideMenu = menuRef.current && !menuRef.current.contains(event.target as Node);
      
      if (isOutsideDropdown && isOutsideMenu) {
        setIsOpen(false);
      }
    }
    window.document.addEventListener("mousedown", handleClickOutside);
    return () => {
      window.document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleAction = async (actionType: 'stop' | 'retry', actionFn: () => Promise<void>) => {
    if (actionType === 'stop') {
      if (!window.confirm('Are you sure you want to stop processing this document?')) {
        return;
      }
    }
    setLoadingAction(actionType);
    setError(null);
    setIsOpen(false);
    try {
      await actionFn();
    } catch (err: any) {
      setError(err.message || `Failed to ${actionType} document`);
    } finally {
      setLoadingAction(null);
    }
  };

  const executeDelete = (permanent: boolean) => {
    const msg = permanent 
      ? 'Are you sure you want to permanently remove this record? This action cannot be undone.'
      : 'Are you sure you want to delete the file? The record will remain, but the file will be permanently deleted from servers.';
    if (window.confirm(msg)) {
      setLoadingAction('delete');
      setError(null);
      setIsOpen(false);
      onDelete(document.id, permanent)
        .then(() => setLoadingAction(null))
        .catch(err => {
         setError(err.message || "Failed to act on document");
         setLoadingAction(null);
      });
    }
  };

  if (loadingAction === 'delete') {
    return (
      <div className="flex justify-center p-2" onClick={(e) => e.stopPropagation()}>
        <span className="material-symbols-outlined text-error animate-spin" style={{ fontVariationSettings: "'FILL' 0" }}>sync</span>
      </div>
    );
  }

  // If other actions are loading
  if (loadingAction) {
    return (
      <div className="flex justify-center p-2" onClick={(e) => e.stopPropagation()}>
        <span className="material-symbols-outlined text-primary animate-spin" style={{ fontVariationSettings: "'FILL' 0" }}>sync</span>
      </div>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button 
        ref={buttonRef}
        onClick={(e) => { 
          e.stopPropagation(); 
          if (!isOpen && buttonRef.current) {
            const rect = buttonRef.current.getBoundingClientRect();
            setDropdownPos({ top: rect.bottom, right: window.innerWidth - rect.right });
          }
          setIsOpen(!isOpen); 
        }}
        className="p-2 rounded-full hover:bg-surface-container-high transition-colors"
      >
        <span className="material-symbols-outlined text-on-surface-variant">more_vert</span>
      </button>

      {isOpen && createPortal(
        <div 
          ref={menuRef}
          onClick={(e) => e.stopPropagation()}
          className="bg-surface-container-lowest border border-outline-variant/20 rounded-lg shadow-lg overflow-hidden z-[9999] flex flex-col py-1"
          style={{ position: 'fixed', top: dropdownPos.top, right: dropdownPos.right, width: '12rem' }}
        >
          <button 
            onClick={() => { setIsOpen(false); navigate(`/documents/${document.id}`); }}
            className="w-full text-left px-4 py-2 text-sm font-medium hover:bg-surface-container-low transition-colors flex items-center gap-2 text-on-surface"
          >
            <span className="material-symbols-outlined text-[18px]">visibility</span> View Details
          </button>

          {(document.status === 'PENDING' || document.status === 'QUEUED' || document.status === 'PROCESSING') && (
            <button 
              onClick={() => handleAction('stop', () => onCancel(document.id))}
              className="w-full text-left px-4 py-2 text-sm font-medium hover:bg-surface-container-low transition-colors flex items-center gap-2 text-orange-600"
            >
              <span className="material-symbols-outlined text-[18px]">stop_circle</span> Stop
            </button>
          )}

          {(document.status === 'FAILED' || document.status === 'CANCELLED' || document.status === 'COMPLETED') && (
            <button 
              onClick={() => handleAction('retry', () => onRetry(document.id))}
              className="w-full text-left px-4 py-2 text-sm font-medium hover:bg-surface-container-low transition-colors flex items-center gap-2 text-primary"
            >
              <span className="material-symbols-outlined text-[18px]">refresh</span> Restart
            </button>
          )}

          <div className="border-t border-outline-variant/10 my-1"></div>

          {(!document.filePath || document.filePath === '') ? (
            <button 
              onClick={() => executeDelete(true)}
              className="w-full text-left px-4 py-2 text-sm font-medium hover:bg-error/10 transition-colors flex items-center gap-2 text-error"
            >
              <span className="material-symbols-outlined text-[18px]">delete_forever</span> Remove
            </button>
          ) : (
            <button 
              onClick={() => executeDelete(false)}
              className="w-full text-left px-4 py-2 text-sm font-medium hover:bg-error/10 transition-colors flex items-center gap-2 text-error"
            >
              <span className="material-symbols-outlined text-[18px]">delete</span> Delete
            </button>
          )}
          
          {error && <span className="text-xs text-error px-4 py-1">{error}</span>}
        </div>,
        window.document.body
      )}
    </div>
  );
}
