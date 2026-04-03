import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { SignIn, SignUp, SignedIn, SignedOut, UserButton } from '@clerk/clerk-react';
import { UploadPage } from './pages/UploadPage';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { motion } from 'framer-motion';

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
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full -z-10 overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-200/30 blur-[120px]"></div>
          <div className="absolute top-[20%] right-[-5%] w-[400px] h-[400px] rounded-full bg-violet-200/30 blur-[100px]"></div>
          <div className="absolute bottom-[10%] left-[20%] w-[600px] h-[600px] rounded-full bg-blue-100/20 blur-[150px]"></div>
        </div>

        <section className="min-h-[870px] flex flex-col items-center justify-center text-center px-6 pt-20 pb-12">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col items-center"
          >
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary-fixed/50 text-on-primary-fixed-variant text-sm font-bold tracking-wide mb-8 border border-primary/10">
              <span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>bolt</span>
              ⚡ AI-Powered Document Intelligence
            </div>

            <h1 className="text-5xl md:text-7xl lg:text-8xl font-black tracking-[-0.04em] text-on-surface leading-[1.1] mb-6 max-w-5xl">
              Transform Documents <br/>
              <span className="signature-text-gradient">Into Insights</span>
            </h1>

            <p className="text-xl md:text-2xl text-on-surface-variant max-w-2xl mx-auto mb-12 font-medium leading-relaxed">
              Upload any document. Our intelligent pipeline extracts, categorizes, and structures your data — with real-time progress tracking.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
              <Link to="/sign-in" className="px-10 py-5 text-xl font-bold text-white signature-gradient rounded-[2rem] shadow-2xl shadow-indigo-500/20 hover:scale-[1.02] active:scale-95 transition-all flex items-center gap-3">
                Get Started Free
                <span className="material-symbols-outlined">arrow_forward</span>
              </Link>
            </div>
          </motion.div>

          <div className="mt-20 w-full max-w-6xl mx-auto px-4">
            <motion.div 
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.8 }}
              className="glass-card rounded-lg p-4 shadow-2xl relative overflow-hidden"
            >
              <img alt="DocFlow Dashboard Preview" className="rounded-md w-full object-cover aspect-[16/8] shadow-sm" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBGHpYqsKorImjTm6S8NLmnlg30tFpedo59Xz6OgwVZU_uWTm97L9nLsQ375Fk4PBkzlo3kWh-_WgxEOUakS6xzJc6JEUexlmKTIGZZw58GEiKnsDK1YdQGecod6awDjEa59egftgbFg5l8Vo-S9cEyCMzFXnTyoS7ykcDrjAoB-7rNivTglUEDli3GaESuZQMDlFiiK4pOzHvCbfVYLsvu-F_tXzCnlLhlL3MUpz7VXx-e_qClRaav7RdOAq19HZ1zuc_n6RdGCg"/>
            </motion.div>
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-8 py-24">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="glass-card rounded-lg p-10 flex flex-col items-start hover:bg-white/90 transition-all group border-transparent hover:border-indigo-100">
              <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center mb-8 group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-indigo-600 text-3xl">description</span>
              </div>
              <h3 className="text-2xl font-bold mb-4 text-on-surface">Smart Extraction</h3>
              <p className="text-on-surface-variant leading-relaxed font-medium">
                Automatically identify and extract key fields from invoices, contracts, and IDs with 99% accuracy using our neural engine.
              </p>
            </div>
            <div className="glass-card rounded-lg p-10 flex flex-col items-start hover:bg-white/90 transition-all group border-transparent hover:border-violet-100">
              <div className="w-14 h-14 rounded-2xl bg-violet-50 flex items-center justify-center mb-8 group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-violet-600 text-3xl">bolt</span>
              </div>
              <h3 className="text-2xl font-bold mb-4 text-on-surface">Real-time Tracking</h3>
              <p className="text-on-surface-variant leading-relaxed font-medium">
                Watch as your documents move through our pipeline. Every step of extraction and validation is visible instantly.
              </p>
            </div>
            <div className="glass-card rounded-lg p-10 flex flex-col items-start hover:bg-white/90 transition-all group border-transparent hover:border-blue-100">
              <div className="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center mb-8 group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-blue-600 text-3xl">shield</span>
              </div>
              <h3 className="text-2xl font-bold mb-4 text-on-surface">Secure Pipeline</h3>
              <p className="text-on-surface-variant leading-relaxed font-medium">
                Enterprise-grade encryption for all data at rest and in transit. Your sensitive documents are processed in isolated enclaves.
              </p>
            </div>
          </div>
        </section>

        <section className="py-12 border-y border-slate-200/10">
          <div className="max-w-7xl mx-auto px-8 flex flex-col items-center">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400 mb-8">Trusted by Global Teams</p>
            <div className="flex flex-wrap justify-center gap-12 opacity-40 grayscale contrast-125">
              <span className="text-2xl font-black">VELOCITY</span>
              <span className="text-2xl font-black">NEXUS</span>
              <span className="text-2xl font-black">QUANTUM</span>
              <span className="text-2xl font-black">ORBIT</span>
              <span className="text-2xl font-black">PRISM</span>
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
        <header className="fixed top-0 w-full z-50 sticky bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl shadow-[0_20px_50px_-12px_rgba(79,70,229,0.08)]">
          <div className="flex justify-between items-center px-8 py-4 max-w-7xl mx-auto">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2 text-2xl font-extrabold tracking-tighter bg-gradient-to-br from-indigo-600 to-violet-600 bg-clip-text text-transparent">
                <div className="w-10 h-10 rounded-xl signature-gradient flex items-center justify-center text-white shadow-lg shadow-indigo-200/50">
                  <span className="material-symbols-outlined">description</span>
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
                <Link to="/sign-in" className="px-5 py-2 text-slate-600 font-semibold hover:bg-slate-100/50 rounded-xl transition-all active:scale-95">Sign In</Link>
                <Link to="/sign-up" className="px-6 py-2.5 signature-gradient text-white font-bold rounded-xl shadow-lg shadow-indigo-200/50 hover:opacity-90 active:scale-95 transition-all">Sign Up</Link>
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
