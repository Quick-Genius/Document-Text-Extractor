import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { SignIn, SignUp, SignedIn, SignedOut, UserButton } from '@clerk/clerk-react';
import { UploadPage } from './pages/UploadPage';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { motion } from 'framer-motion';
import { InteractiveShowcase } from './components/landing/InteractiveShowcase';

function NavLink({ to, children }: { to: string; children: string }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link
      to={to}
      className={`font-['Inter'] font-semibold tracking-tight transition-colors
        ${isActive
          ? 'text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 pb-1'
          : 'text-slate-500 dark:text-slate-400 hover:text-indigo-500'}`}
    >
      {children}
    </Link>
  );
}

function LandingHero() {
  return (
    <>
      <main className="relative">
        {/* Dynamic mesh gradients for background depth */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full -z-10 overflow-hidden pointer-events-none">
          <div className="absolute top-[-5%] left-[-15%] w-[600px] h-[600px] rounded-full bg-indigo-500/15 blur-[120px] dark:bg-indigo-500/10"></div>
          <div className="absolute top-[15%] right-[-10%] w-[500px] h-[500px] rounded-full bg-purple-500/15 blur-[100px] dark:bg-purple-500/10"></div>
          <div className="absolute bottom-[20%] left-[10%] w-[700px] h-[700px] rounded-full bg-blue-500/10 blur-[150px] dark:bg-blue-500/5"></div>
        </div>

        <section className="min-h-[850px] flex flex-col items-center justify-center text-center px-6 pt-32 pb-12">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col items-center"
          >
            {/* Tech Pill Badge */}
            <div className="inline-flex items-center gap-2.5 px-4.5 py-2 rounded-full bg-slate-900/5 dark:bg-white/5 backdrop-blur-md border border-slate-200/40 dark:border-white/10 shadow-sm text-indigo-600 dark:text-indigo-400 text-xs font-bold uppercase tracking-widest mb-8 hover:bg-slate-900/10 dark:hover:bg-white/10 transition-colors">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
              </span>
              AI-Powered Document Intelligence
            </div>

            {/* Title */}
            <h1 className="text-5xl md:text-7xl lg:text-8xl font-black tracking-[-0.04em] text-slate-900 dark:text-white leading-[1.05] mb-6 max-w-5xl">
              Transform Documents <br/>
              <span className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 bg-clip-text text-transparent">
                Into Actionable Insights
              </span>
            </h1>

            {/* Subtitle */}
            <p className="text-lg md:text-xl text-slate-500 dark:text-slate-400 max-w-2xl mx-auto mb-10 font-medium leading-relaxed font-sans">
              Ingest any PDF, DOCX, or image. Our intelligent extraction pipeline parses text, classifies document types, and structures data in real-time.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-4 items-center justify-center mb-16">
              <Link
                to="/sign-in"
                className="px-8 py-4 text-base font-bold text-white signature-gradient rounded-full shadow-lg shadow-indigo-500/20 hover:shadow-[0_0_35px_rgba(79,70,229,0.35)] hover:scale-[1.02] active:scale-95 transition-all flex items-center gap-2"
              >
                Get Started Free
                <span className="material-symbols-outlined text-lg">arrow_forward</span>
              </Link>
              <button
                onClick={() => {
                  document.getElementById('showcase-section')?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="px-8 py-4 text-base font-bold text-slate-700 dark:text-slate-200 bg-white/80 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800/80 active:scale-95 transition-all flex items-center gap-2"
              >
                Explore Live Demo
                <span className="material-symbols-outlined text-lg">play_circle</span>
              </button>
            </div>
          </motion.div>

          {/* Interactive Showcase Container (Replaces old static image) */}
          <div id="showcase-section" className="w-full max-w-6xl mx-auto px-4 scroll-mt-28">
            <motion.div
              initial={{ opacity: 0, y: 45 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            >
              <InteractiveShowcase />
            </motion.div>
          </div>
        </section>

        {/* Bento Grid Feature Section */}
        <section className="max-w-7xl mx-auto px-6 py-28 border-t border-slate-250/10 dark:border-slate-850">
          <div className="text-center mb-16">
            <span className="text-xs font-bold text-indigo-500 uppercase tracking-widest">Platform Capabilities</span>
            <h2 className="text-3xl md:text-5xl font-black text-slate-900 dark:text-white mt-2 tracking-tight">
              Engineered for Modern Teams
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="glass-card rounded-2xl p-8 flex flex-col items-start hover:-translate-y-1 transition-all duration-300 group border-slate-200/20 dark:border-slate-850 hover:border-indigo-500/30 hover:shadow-2xl hover:shadow-indigo-500/5">
              <div className="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-8 group-hover:scale-110 group-hover:bg-indigo-500 group-hover:text-white transition-all duration-300">
                <span className="material-symbols-outlined text-2xl">psychology</span>
              </div>
              <h3 className="text-xl font-bold mb-3 text-slate-900 dark:text-white">Smart OCR Extraction</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed font-medium">
                Automatically extract metadata, tables, invoices, contracts, and dates using our high-fidelity layout-aware neural parsing engine.
              </p>
            </div>

            <div className="glass-card rounded-2xl p-8 flex flex-col items-start hover:-translate-y-1 transition-all duration-300 group border-slate-200/20 dark:border-slate-850 hover:border-violet-500/30 hover:shadow-2xl hover:shadow-violet-500/5">
              <div className="w-12 h-12 rounded-xl bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center mb-8 group-hover:scale-110 group-hover:bg-violet-500 group-hover:text-white transition-all duration-300">
                <span className="material-symbols-outlined text-2xl">bolt</span>
              </div>
              <h3 className="text-xl font-bold mb-3 text-slate-900 dark:text-white">Real-Time Sync</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed font-medium">
                Monitor files processing inside Celery workers. Watch OCR, categorization, and validation stages happen in real-time.
              </p>
            </div>

            <div className="glass-card rounded-2xl p-8 flex flex-col items-start hover:-translate-y-1 transition-all duration-300 group border-slate-200/20 dark:border-slate-850 hover:border-emerald-500/30 hover:shadow-2xl hover:shadow-emerald-500/5">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-8 group-hover:scale-110 group-hover:bg-emerald-500 group-hover:text-white transition-all duration-300">
                <span className="material-symbols-outlined text-2xl">shield</span>
              </div>
              <h3 className="text-xl font-bold mb-3 text-slate-900 dark:text-white">Secure Sandbox</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed font-medium">
                Documents are processed in isolated worker enclaves. 256-bit encryption secures all documents in transit and storage bucket environments.
              </p>
            </div>
          </div>
        </section>

        {/* Logo Cloud Section */}
        <section className="py-16 border-y border-slate-200/10 bg-slate-50/50 dark:bg-slate-950/20">
          <div className="max-w-7xl mx-auto px-8 flex flex-col items-center">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400 mb-8">Trusted by Global Teams</p>
            <div className="flex flex-wrap justify-center gap-12 opacity-40 grayscale contrast-125">
              <span className="text-2xl font-black text-slate-700 dark:text-slate-350 tracking-tighter">VELOCITY</span>
              <span className="text-2xl font-black text-slate-700 dark:text-slate-350 tracking-tighter">NEXUS</span>
              <span className="text-2xl font-black text-slate-700 dark:text-slate-350 tracking-tighter">QUANTUM</span>
              <span className="text-2xl font-black text-slate-700 dark:text-slate-350 tracking-tighter">ORBIT</span>
              <span className="text-2xl font-black text-slate-700 dark:text-slate-350 tracking-tighter">PRISM</span>
            </div>
          </div>
        </section>
      </main>

      <footer className="w-full border-t border-slate-200/20 bg-slate-50 dark:bg-slate-950">
        <div className="flex flex-col md:flex-row justify-between items-center px-8 py-12 max-w-7xl mx-auto gap-6">
          <div className="flex flex-col gap-2 items-center md:items-start">
            <span className="font-bold text-slate-900 dark:text-white text-xl">DocFlow</span>
            <p className="font-['Inter'] text-sm text-slate-500 dark:text-slate-400 max-w-xs text-center md:text-left">
              Processing the world's unstructured data with sophisticated intelligence.
            </p>
          </div>
          <div className="flex items-center gap-8">
            <a className="text-slate-500 hover:text-indigo-500 hover:underline transition-all font-['Inter'] text-sm" href="#">Terms</a>
            <a className="text-slate-500 hover:text-indigo-500 hover:underline transition-all font-['Inter'] text-sm" href="#">Privacy</a>
            <a className="text-slate-500 hover:text-indigo-500 hover:underline transition-all font-['Inter'] text-sm" href="#">Documentation</a>
            <a className="text-slate-500 hover:text-indigo-500 hover:underline transition-all font-['Inter'] text-sm" href="#">Support</a>
          </div>
          <p className="font-['Inter'] text-sm text-slate-500 dark:text-slate-400">
            © 2024 DocFlow AI. Built for Sophisticated Air.
          </p>
        </div>
      </footer>
    </>
  );
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-background font-body text-on-surface selection:bg-primary-fixed selection:text-primary overflow-x-hidden">
        <header className="fixed top-0 w-full z-50 bg-white/70 dark:bg-slate-950/70 backdrop-blur-md border-b border-slate-200/10 shadow-sm">
          <div className="flex justify-between items-center px-8 py-4 max-w-7xl mx-auto">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2 text-2xl font-extrabold tracking-tighter bg-gradient-to-br from-indigo-600 to-violet-600 bg-clip-text text-transparent">
                <div className="w-9 h-9 rounded-xl signature-gradient flex items-center justify-center text-white shadow-lg shadow-indigo-500/25">
                  <span className="material-symbols-outlined text-[20px]">description</span>
                </div>
                DocFlow
              </Link>
              
              <SignedIn>
                <nav className="hidden md:flex items-center gap-6">
                  <NavLink to="/">Upload</NavLink>
                  <NavLink to="/dashboard">Dashboard</NavLink>
                </nav>
              </SignedIn>
            </div>

            <div className="flex items-center gap-4">
              <SignedIn>
                <button className="p-2 hover:bg-slate-100/50 dark:hover:bg-slate-800/50 rounded-xl transition-all active:scale-95 duration-200 ease-in-out">
                  <span className="material-symbols-outlined text-on-surface-variant">notifications</span>
                </button>
                <div className="pl-4 border-l border-outline-variant/20">
                  <UserButton
                    afterSignOutUrl="/"
                    appearance={{
                      elements: {
                        avatarBox: 'w-10 h-10 ring-2 ring-primary-container/20',
                      },
                    }}
                  />
                </div>
              </SignedIn>
              <SignedOut>
                <Link to="/sign-in" className="px-5 py-2 text-slate-650 dark:text-slate-350 font-semibold hover:bg-slate-100/50 dark:hover:bg-slate-800/30 rounded-xl transition-all active:scale-95">Sign In</Link>
                <Link to="/sign-up" className="px-6 py-2.5 signature-gradient text-white font-bold rounded-xl shadow-md shadow-indigo-500/15 hover:shadow-indigo-500/25 hover:opacity-95 active:scale-[0.98] transition-all">Sign Up</Link>
              </SignedOut>
            </div>
          </div>
        </header>

        <main>
          <Routes>
            <Route path="/sign-in/*" element={
              <div className="flex flex-col items-center justify-center min-h-[calc(100vh-80px)] pt-20">
                <SignIn routing="path" path="/sign-in" />
              </div>
            } />
            <Route path="/sign-up/*" element={
              <div className="flex flex-col items-center justify-center min-h-[calc(100vh-80px)] pt-20">
                <SignUp routing="path" path="/sign-up" />
              </div>
            } />
            <Route
              path="/"
              element={
                <>
                  <SignedOut>
                    <LandingHero />
                  </SignedOut>
                  <SignedIn>
                    <UploadPage />
                  </SignedIn>
                </>
              }
            />
            <Route path="/dashboard" element={<SignedIn><DashboardPage /></SignedIn>} />
            <Route path="/documents/:id" element={<SignedIn><DocumentDetailPage /></SignedIn>} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
