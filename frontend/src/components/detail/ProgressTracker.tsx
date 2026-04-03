import { motion } from 'framer-motion';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useAuth } from '@clerk/clerk-react';
import { useEffect, useState } from 'react';

interface ProgressTrackerProps {
  job: any;
}

const STAGES = [
  { id: 'job_started', label: 'Initialized', icon: 'check_circle' },
  { id: 'parsing_started', label: 'Parsing', icon: 'file_open' },
  { id: 'extraction_started', label: 'Extraction', icon: 'memory' },
  { id: 'storing_results', label: 'Storing', icon: 'database' },
  { id: 'job_completed', label: 'Completed', icon: 'task_alt' },
];

export function ProgressTracker({ job }: ProgressTrackerProps) {
  const { userId } = useAuth();
  const { subscribe, unsubscribe, lastMessage } = useWebSocket(userId || '');
  const [currentProgress, setCurrentProgress] = useState({
    status: job.status,
    progress: job.status === 'COMPLETED' ? 100 : 0,
    message: 'Waiting for update...',
  });

  useEffect(() => {
    if (job.id) {
      subscribe(job.id);
      return () => unsubscribe(job.id);
    }
  }, [job.id, subscribe, unsubscribe]);

  useEffect(() => {
    if (lastMessage && lastMessage.jobId === job.id) {
      setCurrentProgress({
        status: lastMessage.data?.status || lastMessage.type,
        progress: Number(lastMessage.data?.progress) || 0,
        message: lastMessage.data?.message || '',
      });
    }
  }, [lastMessage, job.id]);

  const activeStageIndex = STAGES.findIndex(s => 
    s.id === currentProgress.status || 
    (currentProgress.status === 'COMPLETED' && s.id === 'job_completed')
  );

  const activeIndexToUse = activeStageIndex === -1 ? 0 : activeStageIndex;
  const progressPercentage = (Math.max(0, activeIndexToUse) / (STAGES.length - 1)) * 100;

  return (
    <div className="space-y-10">
      {/* Progress Tracker Horizontal Chart */}
      <div className="relative flex justify-between items-center mb-12">
        {/* Background line */}
        <div className="absolute h-0.5 w-full bg-white/20 top-[20px] -translate-y-1/2 left-0 z-0"></div>
        {/* Active progress line */}
        <motion.div 
          className="absolute h-0.5 bg-white top-[20px] -translate-y-1/2 left-0 z-0"
          initial={{ width: 0 }}
          animate={{ width: `${progressPercentage}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />

        {/* Stages */}
        {STAGES.map((stage, idx) => {
          const isCompleted = idx < activeIndexToUse || currentProgress.status === 'COMPLETED';
          const isActive = idx === activeIndexToUse && currentProgress.status !== 'COMPLETED';

          return (
            <div key={stage.id} className="relative z-10 flex flex-col items-center gap-3">
              {isCompleted ? (
                <div className="w-10 h-10 bg-white text-primary rounded-full flex items-center justify-center shadow-lg transition-all transform hover:scale-110">
                  <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                </div>
              ) : isActive ? (
                <div className="w-12 h-12 bg-primary ring-4 ring-white ring-offset-4 ring-offset-primary-container rounded-full flex items-center justify-center shadow-2xl animate-pulse">
                  <span className="material-symbols-outlined text-white animate-spin" style={{ fontVariationSettings: "'FILL' 0" }}>sync</span>
                </div>
              ) : (
                <div className="w-10 h-10 bg-white/20 text-white/50 rounded-full flex items-center justify-center border border-white/10">
                  <span className="material-symbols-outlined text-xl">{stage.icon}</span>
                </div>
              )}
              
              <span className={`text-xs ${isActive ? 'font-bold text-white' : isCompleted ? 'font-semibold text-white/90' : 'font-semibold text-white/50'}`}>
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="space-y-4">
        <div className="flex justify-between items-end">
          <div className="space-y-1">
            <p className="text-sm font-medium opacity-80">Overall Progress</p>
            <p className="text-5xl font-black tracking-tight">{currentProgress.progress}%</p>
          </div>
          <p className="text-sm italic opacity-70 mb-2">{currentProgress.message || 'Processing...'}</p>
        </div>
        
        <div className="h-3 w-full bg-white/20 rounded-full overflow-hidden">
          <motion.div 
            className="h-full bg-white rounded-full shadow-[0_0_15px_rgba(255,255,255,0.5)]"
            initial={{ width: 0 }}
            animate={{ width: `${currentProgress.progress}%` }}
            transition={{ type: 'spring', stiffness: 50 }}
          />
        </div>
      </div>

      {currentProgress.status === 'FAILED' && (
        <div className="mt-8 bg-error-container text-on-error-container border border-error/20 rounded-xl p-6 flex gap-4 items-start shadow-sm">
          <span className="material-symbols-outlined text-3xl text-error mt-1">report</span>
          <div className="flex flex-col gap-1 text-left">
            <span className="text-sm font-bold tracking-tight text-error">Processing Interrupted</span>
            <p className="text-sm text-on-error-container/90">The system encountered an error while processing this document. Ensure the file is not corrupted and try again.</p>
          </div>
        </div>
      )}
    </div>
  );
}
