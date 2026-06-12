import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface ExtractField {
  label: string;
  key: string;
  value: string;
  confidence: number;
  icon: string;
}

interface DocTemplate {
  name: string;
  filename: string;
  fileSize: string;
  type: string;
  fields: ExtractField[];
  json: string;
  htmlContent: React.ReactNode;
}

export function InteractiveShowcase() {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [rightTab, setRightTab] = useState<'fields' | 'json'>('fields');
  const [processState, setProcessState] = useState<'uploading' | 'ocr' | 'extracting' | 'done'>('uploading');
  const [progress, setProgress] = useState(0);
  const [isAutoplay, setIsAutoplay] = useState(true);
  const autoplayTimer = useRef<any>(null);
  const cycleTimer = useRef<any>(null);

  const templates: DocTemplate[] = [
    {
      name: 'Acme Invoice',
      filename: 'invoice_INV-2024-001.pdf',
      fileSize: '142 KB',
      type: 'Invoice / Receipt',
      fields: [
        { label: 'Invoice ID', key: 'invoice_id', value: 'INV-2024-001', confidence: 99.9, icon: 'tag' },
        { label: 'Vendor Name', key: 'vendor', value: 'ACME Corp', confidence: 99.4, icon: 'store' },
        { label: 'Invoice Date', key: 'date', value: '2026-06-12', confidence: 98.7, icon: 'calendar_today' },
        { label: 'Tax Amount', key: 'tax_amount', value: '$1,177.50', confidence: 99.2, icon: 'percent' },
        { label: 'Total Amount', key: 'total_amount', value: '$14,250.00', confidence: 99.8, icon: 'payments' }
      ],
      json: `{
  "document_type": "invoice",
  "invoice_id": "INV-2024-001",
  "vendor": {
    "name": "ACME Corp",
    "address": "123 Industrial Parkway"
  },
  "date": "2026-06-12",
  "items": [
    { "description": "Enterprise AI License", "qty": 1, "total": 12000.00 },
    { "description": "API Gateway Integration", "qty": 5, "total": 2250.00 }
  ],
  "tax": 1177.50,
  "total_amount": 14250.00,
  "confidence_score": 0.994
}`,
      htmlContent: (
        <div className="space-y-4 font-mono text-xs text-slate-300">
          <div className="flex justify-between items-start border-b border-slate-800 pb-4">
            <div>
              <div className="text-lg font-bold text-white tracking-tight">ACME CORP</div>
              <div className="text-slate-500">123 Industrial Parkway</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-slate-400">INVOICE</div>
              <div className="relative inline-block px-1.5 py-0.5 bg-indigo-500/10 border border-indigo-500/30 rounded text-indigo-400 text-xs font-bold mt-1">
                #INV-2024-001
                <span className="absolute -top-4 left-0 text-[8px] uppercase text-indigo-400 font-sans tracking-wide">invoice_id</span>
              </div>
            </div>
          </div>
          <div className="flex justify-between text-[11px] text-slate-400">
            <div>
              <div>Billed To:</div>
              <div className="text-white font-semibold mt-1">DocFlow Technologies</div>
            </div>
            <div className="text-right">
              <div>Date:</div>
              <div className="text-white font-semibold mt-1">2026-06-12</div>
            </div>
          </div>
          <table className="w-full text-left border-collapse mt-4">
            <thead>
              <tr className="border-b border-slate-800 text-[10px] text-slate-500">
                <th className="pb-2">Description</th>
                <th className="pb-2 text-right">Qty</th>
                <th className="pb-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-800/50">
                <td className="py-2 text-slate-300">Enterprise AI License</td>
                <td className="py-2 text-right text-slate-400">1</td>
                <td className="py-2 text-right text-white">$12,000.00</td>
              </tr>
              <tr>
                <td className="py-2 text-slate-300">API Integration</td>
                <td className="py-2 text-right text-slate-400">5</td>
                <td className="py-2 text-right text-white">$2,250.00</td>
              </tr>
            </tbody>
          </table>
          <div className="flex justify-between items-center pt-4 border-t border-slate-800 mt-4">
            <div className="text-slate-500">Tax (8.25%): $1,177.50</div>
            <div className="text-right">
              <div className="text-slate-500 text-[10px]">Total Amount</div>
              <div className="relative inline-block px-1.5 py-0.5 bg-indigo-500/10 border border-indigo-500/30 rounded text-indigo-400 text-sm font-bold">
                $14,250.00
                <span className="absolute -top-4 right-0 text-[8px] uppercase text-indigo-400 font-sans tracking-wide">total_amount</span>
              </div>
            </div>
          </div>
        </div>
      )
    },
    {
      name: 'NDA Contract',
      filename: 'mutual_nda_globex.docx',
      fileSize: '45 KB',
      type: 'Legal Document',
      fields: [
        { label: 'Document Type', key: 'document_type', value: 'NDA Agreement', confidence: 98.2, icon: 'gavel' },
        { label: 'Disclosing Party', key: 'disclosing_party', value: 'DocFlow Corp', confidence: 99.1, icon: 'business' },
        { label: 'Receiving Party', key: 'receiving_party', value: 'Globex Enterprises', confidence: 99.5, icon: 'business' },
        { label: 'Effective Date', key: 'effective_date', value: '2026-05-01', confidence: 99.0, icon: 'event' },
        { label: 'Governing Law', key: 'governing_law', value: 'State of Delaware', confidence: 97.4, icon: 'balance' }
      ],
      json: `{
  "document_type": "mutual_nda",
  "disclosing_party": "DocFlow Corp",
  "receiving_party": "Globex Enterprises",
  "effective_date": "2026-05-01",
  "confidentiality_period": "5 Years",
  "governing_law": {
    "state": "Delaware",
    "country": "USA"
  },
  "confidence_score": 0.986
}`,
      htmlContent: (
        <div className="space-y-4 font-serif text-[10px] text-slate-300 leading-relaxed">
          <div className="text-center font-bold text-white text-xs uppercase tracking-wide border-b border-slate-800 pb-3">
            MUTUAL NON-DISCLOSURE AGREEMENT
          </div>
          <p>
            This Mutual Non-Disclosure Agreement (the "Agreement") is entered into as of{' '}
            <span className="relative inline-block px-1 bg-violet-500/10 border border-violet-500/30 rounded text-violet-400 font-sans font-semibold">
              May 01, 2026
              <span className="absolute -top-4 left-0 text-[7px] uppercase text-violet-400 font-sans tracking-wide">effective_date</span>
            </span>{' '}
            (the "Effective Date"), by and between:
          </p>
          <div className="pl-4 border-l border-slate-850 space-y-1 font-sans">
            <div>
              <span className="text-slate-500">Party A: </span>
              <span className="relative inline-block px-1 bg-violet-500/10 border border-violet-500/30 rounded text-violet-400 font-semibold">
                DocFlow Corp
                <span className="absolute -top-4 left-0 text-[7px] uppercase text-violet-400 font-sans tracking-wide">disclosing_party</span>
              </span>
            </div>
            <div>
              <span className="text-slate-500">Party B: </span>
              <span className="relative inline-block px-1 bg-violet-500/10 border border-violet-500/30 rounded text-violet-400 font-semibold">
                Globex Enterprises
                <span className="absolute -top-4 left-0 text-[7px] uppercase text-violet-400 font-sans tracking-wide">receiving_party</span>
              </span>
            </div>
          </div>
          <p>
            1. <strong className="text-white">Purpose.</strong> The parties wish to explore a business opportunity of mutual interest. In connection with this opportunity, each party may disclose to the other certain proprietary technical and business information.
          </p>
          <p>
            2. <strong className="text-white">Term.</strong> The obligations of confidentiality hereunder shall survive for a period of{' '}
            <span className="text-white font-semibold">5 Years</span> from the Effective Date.
          </p>
          <p>
            3. <strong className="text-white">Governing Law.</strong> This Agreement shall be governed by and construed in accordance with the laws of the{' '}
            <span className="relative inline-block px-1 bg-violet-500/10 border border-violet-500/30 rounded text-violet-400 font-sans font-semibold">
              State of Delaware
              <span className="absolute -top-4 left-0 text-[7px] uppercase text-violet-400 font-sans tracking-wide">governing_law</span>
            </span>.
          </p>
        </div>
      )
    },
    {
      name: 'Retail Receipt',
      filename: 'receipt_2844.png',
      fileSize: '89 KB',
      type: 'Invoice / Receipt',
      fields: [
        { label: 'Merchant', key: 'merchant', value: 'Target Stores', confidence: 99.6, icon: 'shopping_bag' },
        { label: 'Date', key: 'date', value: '2026-06-10', confidence: 98.9, icon: 'today' },
        { label: 'Item Count', key: 'items_count', value: '4 items', confidence: 97.5, icon: 'list_alt' },
        { label: 'Payment Method', key: 'payment_method', value: 'Visa ending 4321', confidence: 99.1, icon: 'credit_card' },
        { label: 'Total Amount', key: 'total_amount', value: '$184.22', confidence: 99.9, icon: 'payments' }
      ],
      json: `{
  "document_type": "receipt",
  "merchant": {
    "name": "Target Stores",
    "address": "Store #2844, San Jose, CA"
  },
  "date": "2026-06-10T14:32:00",
  "items": [
    { "name": "MNDR CL-S BNDR (3PK)", "price": 14.99 },
    { "name": "SMART LED LAMP PRO", "price": 119.00 },
    { "name": "USB-C FAST CHG CBL 2M", "price": 39.98 }
  ],
  "subtotal": 173.97,
  "tax": 10.25,
  "total": 184.22,
  "payment": {
    "type": "Visa",
    "last_four": "4321"
  },
  "confidence_score": 0.99
}`,
      htmlContent: (
        <div className="space-y-3 font-mono text-[10px] text-slate-300 uppercase max-w-[280px] mx-auto">
          <div className="text-center">
            <div className="text-sm font-bold text-white tracking-wider">TARGET STORES</div>
            <div className="text-slate-500 text-[8px] mt-0.5">Store #2844 • San Jose, CA</div>
          </div>
          <div className="border-t border-dashed border-slate-800 my-2 pt-2 flex justify-between text-slate-500 text-[8px]">
            <span>Reg 04 • Cashier #882</span>
            <span>2026-06-10 14:32</span>
          </div>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span>MNDR CL-S BNDR (3PK)</span>
              <span>$14.99 A</span>
            </div>
            <div className="flex justify-between">
              <span>SMART LED LAMP PRO</span>
              <span>$119.00 A</span>
            </div>
            <div className="flex justify-between">
              <span>USB-C FAST CHG CBL 2M</span>
              <span>$39.98 A</span>
            </div>
          </div>
          <div className="border-t border-dashed border-slate-800 pt-2 space-y-1">
            <div className="flex justify-between text-slate-500">
              <span>Subtotal</span>
              <span>$173.97</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Tax (5.9%)</span>
              <span>$10.25</span>
            </div>
            <div className="flex justify-between text-white font-bold text-xs pt-1 border-t border-slate-800 mt-1">
              <span>Total</span>
              <span className="relative inline-block px-1.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-emerald-400 text-xs font-bold">
                $184.22
                <span className="absolute -top-4 right-0 text-[7px] uppercase text-emerald-400 font-sans tracking-wide">total_amount</span>
              </span>
            </div>
          </div>
          <div className="text-center pt-3 opacity-30 flex flex-col items-center">
            <div className="w-40 h-6 bg-slate-800 flex items-center justify-center tracking-[3px] text-[9px] font-semibold text-slate-300">
              |||| | || ||| || |||
            </div>
            <span className="text-[7px] mt-1 text-slate-500 font-sans">Thank you!</span>
          </div>
        </div>
      )
    }
  ];

  // Logic to simulate document extraction timeline
  const runSimulation = () => {
    setProcessState('uploading');
    setProgress(0);

    if (cycleTimer.current) clearInterval(cycleTimer.current);

    let currentProgress = 0;
    cycleTimer.current = setInterval(() => {
      currentProgress += 5;
      setProgress(Math.min(currentProgress, 100));

      if (currentProgress < 25) {
        setProcessState('uploading');
      } else if (currentProgress < 60) {
        setProcessState('ocr');
      } else if (currentProgress < 90) {
        setProcessState('extracting');
      } else {
        setProcessState('done');
        if (cycleTimer.current) clearInterval(cycleTimer.current);
      }
    }, 120);
  };

  useEffect(() => {
    runSimulation();
    return () => {
      if (cycleTimer.current) clearInterval(cycleTimer.current);
    };
  }, [activeTab]);

  // Autoplay functionality
  useEffect(() => {
    if (!isAutoplay) return;

    autoplayTimer.current = setInterval(() => {
      setActiveTab((prev) => (prev + 1) % templates.length);
    }, 8000);

    return () => {
      if (autoplayTimer.current) clearInterval(autoplayTimer.current);
    };
  }, [isAutoplay]);

  const handleTabChange = (index: number) => {
    setIsAutoplay(false);
    if (autoplayTimer.current) clearInterval(autoplayTimer.current);
    setActiveTab(index);
  };

  const getStatusText = () => {
    switch (processState) {
      case 'uploading':
        return 'Ingesting document...';
      case 'ocr':
        return 'Running optical character recognition...';
      case 'extracting':
        return 'AI extraction in progress...';
      case 'done':
        return 'Parsing completed successfully!';
    }
  };

  return (
    <div className="w-full">
      {/* Sample Selector Tabs */}
      <div className="flex flex-wrap gap-2 justify-center mb-8">
        {templates.map((template, idx) => {
          const isActive = idx === activeTab;
          return (
            <button
              key={template.name}
              onClick={() => handleTabChange(idx)}
              className={`px-5 py-2.5 rounded-full text-sm font-semibold tracking-tight transition-all flex items-center gap-2 relative ${
                isActive
                  ? 'text-white'
                  : 'text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100/50 dark:hover:bg-slate-800/30'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="activeTabIndicator"
                  className="absolute inset-0 signature-gradient rounded-full -z-10 shadow-lg shadow-indigo-500/20"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
              <span className="material-symbols-outlined text-[18px]">
                {idx === 0 ? 'receipt_long' : idx === 1 ? 'article' : 'confirmation_number'}
              </span>
              {template.name}
            </button>
          );
        })}
      </div>

      {/* Main Showcase Panel */}
      <div className="glass-card rounded-2xl p-6 border border-slate-200/20 shadow-[0_30px_70px_-15px_rgba(79,70,229,0.12)]">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Panel: Document Viewer */}
          <div className="lg:col-span-7 flex flex-col">
            <div className="flex items-center justify-between mb-4 px-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-ping"></span>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Document Analyzer (Live)
                </span>
              </div>
              <div className="text-xs text-slate-400 bg-slate-100 dark:bg-slate-850 px-2.5 py-1 rounded-md font-mono">
                {templates[activeTab].filename} ({templates[activeTab].fileSize})
              </div>
            </div>

            {/* Document Frame */}
            <div className="relative flex-grow bg-slate-950 rounded-xl border border-slate-900 p-6 shadow-inner min-h-[380px] flex flex-col justify-center overflow-hidden">
              
              {/* Scan Laser Line */}
              {processState === 'ocr' && (
                <motion.div
                  className="absolute left-0 right-0 h-[3px] bg-gradient-to-r from-transparent via-indigo-400 to-transparent z-15 shadow-[0_0_15px_#4f46e5]"
                  animate={{ y: [0, 380, 0] }}
                  transition={{
                    duration: 2.2,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                  style={{ top: 0 }}
                />
              )}

              {/* Grid Lines Overlay */}
              <div 
                className="absolute inset-0 opacity-5 pointer-events-none" 
                style={{
                  backgroundImage: `linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)`,
                  backgroundSize: '20px 20px'
                }}
              />

              {/* Processing Overlay states */}
              <AnimatePresence mode="wait">
                {processState === 'uploading' && (
                  <motion.div
                    key="uploading-state"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center text-center p-6"
                  >
                    <div className="relative w-16 h-16 mb-4">
                      <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20"></div>
                      <div className="absolute inset-0 rounded-full border-2 border-t-indigo-500 animate-spin"></div>
                    </div>
                    <h4 className="text-white font-bold text-base mb-1">Ingesting Document</h4>
                    <p className="text-slate-400 text-xs max-w-[220px]">
                      Uploading raw binary contents to parser buffer...
                    </p>
                  </motion.div>
                )}

                {processState === 'ocr' && (
                  <motion.div
                    key="ocr-state"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.3 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-indigo-950/10 pointer-events-none z-10"
                  />
                )}
              </AnimatePresence>

              {/* Document Content Render */}
              <div className={`transition-all duration-300 ${processState === 'uploading' ? 'filter blur-sm opacity-40' : 'opacity-100'}`}>
                {templates[activeTab].htmlContent}
              </div>
            </div>

            {/* Pipeline progress bar */}
            <div className="mt-4 bg-slate-100 dark:bg-slate-900 rounded-lg p-3 border border-slate-200/10">
              <div className="flex justify-between items-center text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">
                <span>{getStatusText()}</span>
                <span>{progress}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                <motion.div
                  className="h-full signature-gradient"
                  style={{ width: `${progress}%` }}
                  transition={{ ease: "easeInOut" }}
                />
              </div>
            </div>
          </div>

          {/* Right Panel: Extracted Output */}
          <div className="lg:col-span-5 flex flex-col">
            
            {/* Header Tabs */}
            <div className="flex border-b border-slate-200/10 mb-4 pb-0.5 justify-between items-center">
              <div className="flex gap-4">
                <button
                  onClick={() => setRightTab('fields')}
                  className={`text-sm font-bold pb-2 transition-all relative ${
                    rightTab === 'fields' ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-400 hover:text-slate-600'
                  }`}
                >
                  Extracted Fields
                  {rightTab === 'fields' && (
                    <motion.div
                      layoutId="activeRightTabIndicator"
                      className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600 dark:bg-indigo-400"
                    />
                  )}
                </button>
                <button
                  onClick={() => setRightTab('json')}
                  className={`text-sm font-bold pb-2 transition-all relative ${
                    rightTab === 'json' ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-400 hover:text-slate-600'
                  }`}
                >
                  Structured JSON
                  {rightTab === 'json' && (
                    <motion.div
                      layoutId="activeRightTabIndicator"
                      className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600 dark:bg-indigo-400"
                    />
                  )}
                </button>
              </div>
              <div className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                AI READY
              </div>
            </div>

            {/* Extracted Details Wrapper */}
            <div className="flex-grow flex flex-col justify-between">
              <AnimatePresence mode="wait">
                {rightTab === 'fields' ? (
                  <motion.div
                    key="fields-panel"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-3"
                  >
                    {templates[activeTab].fields.map((field, index) => {
                      const isComplete = processState === 'done' || (processState === 'extracting' && index < 3);
                      return (
                        <div
                          key={field.key}
                          className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                            isComplete
                              ? 'bg-white/80 dark:bg-slate-900/40 border-slate-200/40 dark:border-slate-850 shadow-sm'
                              : 'bg-slate-50/50 dark:bg-slate-950/20 border-dashed border-slate-200/20 opacity-40'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                              isComplete ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400' : 'bg-slate-100 text-slate-400'
                            }`}>
                              <span className="material-symbols-outlined text-[18px]">
                                {field.icon}
                              </span>
                            </div>
                            <div>
                              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">
                                {field.label}
                              </div>
                              <div className="text-sm font-semibold text-slate-850 dark:text-slate-100 font-mono mt-0.5">
                                {isComplete ? field.value : <span className="animate-pulse">···</span>}
                              </div>
                            </div>
                          </div>
                          
                          {isComplete && (
                            <div className="text-right">
                              <span className="text-[10px] font-extrabold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                                {field.confidence}%
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </motion.div>
                ) : (
                  <motion.div
                    key="json-panel"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                    className="flex-grow flex"
                  >
                    <div className="w-full bg-slate-950 border border-slate-900 rounded-xl p-4 font-mono text-xs text-emerald-400 overflow-x-auto shadow-inner h-[320px] flex flex-col justify-between">
                      {processState !== 'done' ? (
                        <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
                          <span className="material-symbols-outlined animate-spin text-2xl">
                            sync
                          </span>
                          <span>Compiling JSON object...</span>
                        </div>
                      ) : (
                        <pre className="m-0 leading-relaxed max-w-full">
                          <code>
                            {templates[activeTab].json.split('\n').map((line, i) => {
                              // Simple styling helper
                              const hasKey = line.includes(':');
                              if (hasKey) {
                                const parts = line.split(':');
                                const key = parts[0];
                                const val = parts.slice(1).join(':');
                                return (
                                  <span key={i} className="block">
                                    <span className="text-indigo-400">{key}</span>:
                                    <span className="text-emerald-300">{val}</span>
                                  </span>
                                );
                              }
                              return <span key={i} className="block text-slate-400">{line}</span>;
                            })}
                          </code>
                        </pre>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Extra branding under the right sidebar */}
              <div className="mt-6 border-t border-slate-200/10 pt-4 flex justify-between items-center text-xs text-slate-400 font-medium">
                <span className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-indigo-500 text-sm">hub</span>
                  Entity Linking Engine
                </span>
                <span>v1.2.8</span>
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Autoplay Pause Alert */}
      {!isAutoplay && (
        <div className="text-center mt-3 text-[11px] text-slate-400 flex items-center justify-center gap-1">
          <span className="material-symbols-outlined text-[13px]">pause_circle</span>
          Autoplay paused. Click a template tab to switch manually.
        </div>
      )}
    </div>
  );
}
