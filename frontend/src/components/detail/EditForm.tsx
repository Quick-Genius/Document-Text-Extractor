import { useForm } from 'react-hook-form';

interface EditFormProps {
  data: any;
  onSave: (data: any) => void;
  onFinalize?: () => void;
  isReadOnly?: boolean;
}

export function EditForm({ data, onSave, onFinalize, isReadOnly = false }: EditFormProps) {
  const { register, handleSubmit, formState: { isDirty, isSubmitSuccessful } } = useForm({
    defaultValues: data,
  });

  return (
    <form onSubmit={handleSubmit(onSave)} className="grid grid-cols-1 md:grid-cols-2 gap-6">
      
      {/* Unsaved Changes Banner */}
      {!isReadOnly && (isDirty || isSubmitSuccessful) && (
        <div className="md:col-span-2 flex items-center justify-end pt-2">
          {isDirty && (
            <div className="flex items-center gap-2 px-3 py-1 bg-amber-50 text-amber-700 rounded-full border border-amber-200">
              <span className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></span>
              <span className="text-[10px] font-bold tracking-widest uppercase">Unsaved Changes</span>
            </div>
          )}
          {isSubmitSuccessful && !isDirty && (
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200">
              <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
              <span className="text-[10px] font-bold tracking-widest uppercase">Changes Saved</span>
            </div>
          )}
        </div>
      )}

      <div className="md:col-span-2 flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant tracking-wider uppercase">Document Title</label>
        <input
          {...register('title')}
          disabled={isReadOnly}
          className="bg-surface-container-low border-none rounded-xl px-5 py-4 focus:ring-2 focus:ring-primary/20 focus:bg-white transition-all text-on-surface font-medium disabled:opacity-70 outline-none"
          placeholder="Enter document title..."
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant tracking-wider uppercase">Category</label>
        <input
          {...register('category')}
          disabled={isReadOnly}
          className="bg-surface-container-low border-none rounded-xl px-5 py-4 focus:ring-2 focus:ring-primary/20 focus:bg-white transition-all text-on-surface font-medium disabled:opacity-70 outline-none"
          placeholder="e.g. Invoice, Report..."
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant tracking-wider uppercase">Confidence Score</label>
        <div className="bg-surface-container-low border-none rounded-xl px-5 py-4 flex items-center justify-between">
          <span className="font-bold text-primary">{(data.confidenceScore || 0) * 100}%</span>
          {data.confidenceScore > 0.9 ? (
            <span className="material-symbols-outlined text-emerald-500">verified</span>
          ) : (
            <span className="material-symbols-outlined text-amber-500">warning</span>
          )}
        </div>
      </div>

      <div className="md:col-span-2 flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant tracking-wider uppercase">Executive Summary</label>
        <textarea
          {...register('summary')}
          disabled={isReadOnly}
          rows={5}
          className="bg-surface-container-low border-none rounded-xl px-5 py-4 focus:ring-2 focus:ring-primary/20 focus:bg-white transition-all text-on-surface leading-relaxed disabled:opacity-70 resize-none outline-none"
          placeholder="Brief summary of the document content..."
        />
      </div>

      <div className="md:col-span-2 flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant tracking-wider uppercase">Extracted Text</label>
        <textarea
          {...register('extractedText')}
          disabled={isReadOnly}
          rows={12}
          className="bg-surface-container-low border-none rounded-xl px-5 py-4 focus:ring-2 focus:ring-primary/20 focus:bg-white transition-all text-on-surface leading-relaxed disabled:opacity-70 resize-y outline-none font-mono text-sm"
          placeholder="Full extracted text from the document..."
        />
      </div>

      {!isReadOnly && (
        <div className="md:col-span-2 flex items-center justify-end gap-4 pt-4 border-t border-outline-variant/10">
          <button
            type="submit"
            disabled={!isDirty}
            className={`px-8 py-3 rounded-full font-bold text-sm shadow-lg transition-all 
              ${isDirty 
                ? 'bg-primary text-on-primary shadow-indigo-200/50 hover:-translate-y-0.5 active:scale-95' 
                : 'bg-surface-variant text-on-surface-variant cursor-not-allowed shadow-none'}`}
          >
            Save Changes
          </button>
          
          {onFinalize && (
            <button
              type="button"
              onClick={onFinalize}
              className="px-8 py-3 rounded-full font-bold text-sm bg-emerald-600 text-white shadow-lg shadow-emerald-200/50 hover:-translate-y-0.5 transition-all active:scale-95 flex items-center gap-2"
            >
              Finalize Results <span className="material-symbols-outlined text-sm">check</span>
            </button>
          )}
        </div>
      )}
    </form>
  );
}
