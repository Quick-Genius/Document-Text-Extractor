import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadDocuments, processDocumentsBatch } from '../../services/documentService';
import { useApi } from '../../hooks/useApi';
import { motion, AnimatePresence } from 'framer-motion';

interface UploadedDoc {
  id: string;
  originalName: string;
  fileType: string;
  fileSize: number;
  status: string;
}

interface FileUploaderProps {
  onUploadComplete: (documents: any[]) => void;
}

type Step = 'select' | 'uploaded' | 'processing';

export function FileUploader({ onUploadComplete }: FileUploaderProps) {
  const api = useApi();
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Step 2 state
  const [step, setStep] = useState<Step>('select');
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles(prev => [...prev, ...acceptedFiles]);
    setUploadError(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    maxSize: 50 * 1024 * 1024,
    disabled: step !== 'select',
  });

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  // ─── Step 1: Upload files to server (no processing) ────────────────
  const handleUpload = async () => {
    if (files.length === 0) return;

    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);

    try {
      const response = await uploadDocuments(api, files, (p) => setUploadProgress(p));
      const docs: UploadedDoc[] = response.documents.map((d: any) => ({
        id: d.id,
        originalName: d.originalName,
        fileType: d.fileType,
        fileSize: d.fileSize,
        status: d.status,
      }));
      setUploadedDocs(docs);
      setStep('uploaded');
      setFiles([]);
    } catch (err: any) {
      console.error('Upload failed:', err);
      setUploadError(
        err.response?.data?.detail ||
        (err.code === 'ERR_NETWORK'
          ? 'Cannot connect to the server. Please ensure the backend is running.'
          : 'Failed to upload documents. Please try again.')
      );
    } finally {
      setIsUploading(false);
    }
  };

  // ─── Step 2: Trigger processing on uploaded docs ───────────────────
  const handleProcess = async () => {
    setIsProcessing(true);
    setProcessError(null);

    try {
      const ids = uploadedDocs.map(d => d.id);
      await processDocumentsBatch(api, ids);
      onUploadComplete(uploadedDocs as any[]);
    } catch (err: any) {
      console.error('Processing failed:', err);
      setProcessError(
        err.response?.data?.detail ||
        (err.code === 'ERR_NETWORK'
          ? 'Cannot connect to the server. Please ensure the backend is running.'
          : 'Failed to start document processing. Please try again.')
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setStep('select');
    setUploadedDocs([]);
    setFiles([]);
    setUploadError(null);
    setProcessError(null);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  const getFileIcon = (type: string) => {
    if (type.includes('pdf')) return 'picture_as_pdf';
    if (type.includes('image')) return 'image';
    if (type.includes('word') || type.includes('document')) return 'article';
    return 'description';
  };

  // ═══════════════════════════════════════════════════════════════════
  // STEP 2 VIEW: Files uploaded — ask user to process
  // ═══════════════════════════════════════════════════════════════════
  if (step === 'uploaded') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="space-y-6"
      >
        {/* Step indicator */}
        <div className="flex items-center justify-center gap-3 mb-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center text-sm font-bold shadow-md shadow-emerald-200/50">
              <span className="material-symbols-outlined text-lg">check</span>
            </div>
            <span className="text-sm font-bold text-emerald-600">Uploaded</span>
          </div>
          <div className="w-12 h-0.5 bg-gradient-to-r from-emerald-400 to-indigo-400 rounded-full"></div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full signature-gradient text-white flex items-center justify-center text-sm font-bold shadow-lg shadow-indigo-200/50 animate-pulse">
              2
            </div>
            <span className="text-sm font-bold text-primary">Process</span>
          </div>
        </div>

        {/* Success banner */}
        <div className="flex items-center gap-3 p-4 rounded-lg bg-emerald-50 border border-emerald-200/60">
          <span className="material-symbols-outlined text-emerald-600 text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>cloud_done</span>
          <div>
            <p className="font-bold text-emerald-800 text-sm">
              {uploadedDocs.length} file{uploadedDocs.length > 1 ? 's' : ''} uploaded successfully!
            </p>
            <p className="text-emerald-600 text-xs mt-0.5">Files are stored securely. Click below to start AI processing.</p>
          </div>
        </div>

        {/* Uploaded file list */}
        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {uploadedDocs.map((doc, index) => (
            <motion.div
              key={doc.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className="flex items-center gap-4 p-4 bg-surface-container-low rounded-lg border border-outline-variant/10 hover:bg-white hover:shadow-sm transition-all"
            >
              <div className="w-10 h-10 rounded-lg bg-white shadow-sm flex items-center justify-center text-primary flex-shrink-0">
                <span className="material-symbols-outlined">{getFileIcon(doc.fileType)}</span>
              </div>
              <div className="min-w-0 flex-grow">
                <p className="text-sm font-semibold text-on-surface truncate">{doc.originalName}</p>
                <p className="text-xs text-on-surface-variant">{formatFileSize(doc.fileSize)}</p>
              </div>
              <div className="flex-shrink-0">
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Ready
                </span>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Process error */}
        <AnimatePresence>
          {processError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="p-4 rounded-lg bg-error-container flex items-start gap-3 text-on-error-container"
            >
              <span className="material-symbols-outlined mt-0.5">report</span>
              <div className="flex flex-col">
                <span className="text-sm font-bold tracking-tight">Processing Error</span>
                <span className="text-sm">{processError}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            onClick={handleReset}
            disabled={isProcessing}
            className="flex-1 py-3.5 rounded-xl border border-outline-variant/40 font-bold text-on-surface hover:bg-surface-container-low transition-all active:scale-[0.97] disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined text-lg">arrow_back</span>
            Upload Different Files
          </button>
          <button
            onClick={handleProcess}
            disabled={isProcessing}
            className="flex-[2] py-3.5 rounded-xl signature-gradient text-on-primary font-bold shadow-lg shadow-indigo-200/50 hover:opacity-90 transition-all active:scale-[0.97] disabled:opacity-70 flex items-center justify-center gap-2"
          >
            {isProcessing ? (
              <>
                <span className="material-symbols-outlined animate-spin text-lg" style={{ fontVariationSettings: "'FILL' 0" }}>sync</span>
                Initiating Processing...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                Process Documents with AI
              </>
            )}
          </button>
        </div>
      </motion.div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // STEP 1 VIEW: File selection & upload
  // ═══════════════════════════════════════════════════════════════════
  return (
    <>
      {/* Step indicator */}
      <div className="flex items-center justify-center gap-3 mb-6">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full signature-gradient text-white flex items-center justify-center text-sm font-bold shadow-lg shadow-indigo-200/50">
            1
          </div>
          <span className="text-sm font-bold text-primary">Upload</span>
        </div>
        <div className="w-12 h-0.5 bg-outline-variant/30 rounded-full"></div>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-surface-variant text-on-surface-variant flex items-center justify-center text-sm font-bold">
            2
          </div>
          <span className="text-sm font-medium text-on-surface-variant">Process</span>
        </div>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`group relative border-2 border-dashed rounded-lg p-12 transition-all cursor-pointer
          ${isDragActive 
            ? 'border-primary-container/60 bg-primary-fixed/5' 
            : 'border-outline-variant/40 hover:border-primary-container/60 hover:bg-primary-fixed/5'}`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-primary-fixed/30 flex items-center justify-center text-primary transition-transform group-hover:scale-110">
            <span className="material-symbols-outlined text-4xl">upload_file</span>
          </div>
          <div className="space-y-1">
            <p className="text-lg font-semibold text-on-surface">
              {isDragActive ? 'Drop your files here' : 'Click or drag files to upload'}
            </p>
            <p className="text-sm text-on-surface-variant">PDF, DOCX, Images, TXT (Max 50MB per file)</p>
          </div>
        </div>
      </div>

      {/* Selected file list */}
      {files.length > 0 && (
        <div className="mt-8 space-y-3 max-h-64 overflow-y-auto pr-2">
          {files.map((file, index) => (
            <div key={`${file.name}-${index}`} className={`flex items-center justify-between p-4 bg-surface-container-low rounded-md transition-colors ${isUploading ? 'opacity-70' : 'hover:bg-surface-container-high'}`}>
              <div className="flex items-center gap-4 overflow-hidden">
                <div className="flex-shrink-0 w-10 h-10 rounded bg-white flex items-center justify-center text-primary-container shadow-sm">
                  <span className="material-symbols-outlined">{file.type.includes('image') ? 'image' : 'description'}</span>
                </div>
                <div className="truncate min-w-0">
                  <p className="text-sm font-semibold text-on-surface truncate">{file.name}</p>
                  <p className="text-xs text-on-surface-variant">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>
              <div className="flex items-center gap-4 flex-shrink-0">
                {!isUploading && (
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFile(index); }}
                    className="p-1 hover:bg-error-container/20 rounded-full text-error transition-colors"
                  >
                    <span className="material-symbols-outlined text-lg">close</span>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload error */}
      <AnimatePresence>
        {uploadError && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-6 p-4 rounded-md bg-error-container flex items-start gap-3 text-on-error-container"
          >
            <span className="material-symbols-outlined mt-0.5">report</span>
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-tight">Upload Error</span>
              <span className="text-sm">{uploadError}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upload progress */}
      {isUploading && (
        <div className="mt-6 space-y-2">
          <div className="flex justify-between text-sm font-medium">
            <span className="text-primary flex items-center gap-2">
              <span className="material-symbols-outlined animate-spin text-lg" style={{ fontVariationSettings: "'FILL' 0" }}>sync</span>
              Uploading to server...
            </span>
            <span className="text-on-surface-variant font-bold">{uploadProgress}%</span>
          </div>
          <div className="w-full h-1.5 bg-surface-container rounded-full overflow-hidden">
            <div
              className="h-full signature-gradient transition-all duration-300 ease-out"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Upload button (step 1 only) */}
      <button
        onClick={handleUpload}
        disabled={files.length === 0 || isUploading}
        className={`w-full mt-10 py-4 rounded-md font-bold text-lg shadow-lg active:scale-[0.98] transition-all flex items-center justify-center gap-2
          ${files.length === 0 || isUploading
            ? 'bg-surface-variant text-on-surface-variant cursor-not-allowed shadow-none'
            : 'signature-gradient text-on-primary hover:opacity-90 shadow-indigo-200/50'}`}
      >
        <span className="material-symbols-outlined">{isUploading ? 'sync' : 'cloud_upload'}</span>
        {isUploading ? 'Uploading...' : 'Upload Documents'}
      </button>
    </>
  );
}
