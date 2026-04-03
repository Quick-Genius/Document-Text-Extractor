import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUploader } from '../components/upload/FileUploader';
import { motion, AnimatePresence } from 'framer-motion';

export function UploadPage() {
  const navigate = useNavigate();
  const [uploadedDocs, setUploadedDocs] = useState<any[]>([]);

  const handleUploadComplete = (documents: any[]) => {
    setUploadedDocs(documents);
  };

  return (
    <>
      <main className="flex-grow pt-12 pb-20 px-6">
        <div className="max-w-4xl mx-auto">
          {/* Page Title Section */}
          <div className="text-center mb-12 space-y-4">
            <span className="inline-flex items-center px-4 py-1.5 rounded-full bg-primary-fixed text-primary text-xs font-bold tracking-widest uppercase mb-4">
              ✨ Intelligent Processing
            </span>
            <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-on-surface">
              Upload your <span className="signature-text-gradient">Documents</span>
            </h1>
            <p className="text-on-surface-variant max-w-lg mx-auto leading-relaxed">
              Transform raw data into structured insights. Drop your files below and let our AI engine handle the heavy lifting.
            </p>
          </div>

          <AnimatePresence mode="wait">
            {uploadedDocs.length === 0 ? (
              <motion.section
                key="uploader"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.4 }}
                className="glass-card rounded-lg p-8 shadow-[0_20px_50px_-12px_rgba(79,70,229,0.08)] mb-12"
              >
                <FileUploader onUploadComplete={handleUploadComplete} />
              </motion.section>
            ) : (
              <motion.section
                key="success"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="glass-card rounded-lg p-12 shadow-[0_20px_50px_-12px_rgba(79,70,229,0.08)] mb-12 text-center border-emerald-200"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
                  className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl shadow-emerald-200/50"
                >
                  <span className="material-symbols-outlined text-4xl text-emerald-600">check_circle</span>
                </motion.div>
                <h2 className="text-3xl font-black text-on-surface mb-3">Processing Started!</h2>
                <p className="text-on-surface-variant mb-10 text-lg max-w-md mx-auto">
                  {uploadedDocs.length} document{uploadedDocs.length > 1 ? 's have' : ' has'} been uploaded and queued for AI processing. Track progress in the dashboard.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <button
                    onClick={() => setUploadedDocs([])}
                    className="px-8 py-3.5 rounded-xl border border-outline-variant/40 font-bold text-on-surface hover:bg-surface-container-low transition-all active:scale-[0.97]"
                  >
                    Upload More
                  </button>
                  <button
                    onClick={() => navigate('/dashboard')}
                    className="px-8 py-3.5 rounded-xl signature-gradient text-on-primary font-bold shadow-lg shadow-indigo-200/50 hover:opacity-90 transition-all flex items-center justify-center gap-2 active:scale-[0.97]"
                  >
                    Go to Dashboard <span className="material-symbols-outlined">arrow_forward</span>
                  </button>
                </div>
              </motion.section>
            )}
          </AnimatePresence>

          {/* Feature Cards (Asymmetric/Bento Style) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-8 rounded-lg bg-surface-container-low border border-outline-variant/10 flex flex-col gap-4 group hover:bg-white hover:shadow-xl transition-all">
              <div className="w-12 h-12 rounded-xl signature-gradient flex items-center justify-center text-white">
                <span className="material-symbols-outlined">psychology</span>
              </div>
              <h3 className="font-bold text-xl text-on-surface">Auto-Extraction</h3>
              <p className="text-sm text-on-surface-variant leading-relaxed">Our neural networks automatically pull key-value pairs, tables, and dates with 99.9% accuracy.</p>
            </div>
            <div className="p-8 rounded-lg bg-surface-container-low border border-outline-variant/10 flex flex-col gap-4 group hover:bg-white hover:shadow-xl transition-all">
              <div className="w-12 h-12 rounded-xl signature-gradient flex items-center justify-center text-white">
                <span className="material-symbols-outlined">category</span>
              </div>
              <h3 className="font-bold text-xl text-on-surface">Smart Categorization</h3>
              <p className="text-sm text-on-surface-variant leading-relaxed">Files are instantly tagged and sorted into the correct workflow folders based on content intent.</p>
            </div>
            <div className="p-8 rounded-lg bg-surface-container-low border border-outline-variant/10 flex flex-col gap-4 group hover:bg-white hover:shadow-xl transition-all">
              <div className="w-12 h-12 rounded-xl signature-gradient flex items-center justify-center text-white">
                <span className="material-symbols-outlined">bolt</span>
              </div>
              <h3 className="font-bold text-xl text-on-surface">Real-time Updates</h3>
              <p className="text-sm text-on-surface-variant leading-relaxed">Track every step of the processing stage with live progress updates and instant notifications.</p>
            </div>
          </div>
        </div>
      </main>

      <footer className="w-full border-t border-outline-variant/20 bg-surface-container-low">
        <div className="flex flex-col md:flex-row justify-between items-center px-8 py-12 max-w-7xl mx-auto gap-6">
          <div className="space-y-2 text-center md:text-left">
            <p className="font-bold text-on-surface">DocFlow AI</p>
            <p className="font-['Inter'] text-sm text-on-surface-variant">© 2024 DocFlow AI. Built for Sophisticated Air.</p>
          </div>
          <nav className="flex flex-wrap justify-center gap-8">
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all">Terms</a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all">Privacy</a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all">Documentation</a>
            <a href="#" className="text-on-surface-variant hover:text-primary hover:underline transition-all">Support</a>
          </nav>
        </div>
      </footer>
    </>
  );
}
