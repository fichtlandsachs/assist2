import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Outlet } from 'react-router';
import { Toaster } from 'sonner';
import { Menu, X } from 'lucide-react';

export function Layout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-[#FDFBF7] text-[#231F1F] font-sans overflow-hidden">
      {/* Sidebar - Responsive Backdrop */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <div className={`
        fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 lg:relative lg:translate-x-0
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <Sidebar onClose={() => setIsSidebarOpen(false)} />
      </div>

      <main className="flex-1 overflow-y-auto custom-scrollbar relative w-full">
        <header className="h-16 border-b-2 border-slate-900/5 flex items-center justify-between px-6 lg:px-10 bg-[#FDFBF7]/80 backdrop-blur-md sticky top-0 z-30">
          <div className="flex items-center gap-4">
             {/* Mobile Menu Toggle */}
             <button 
               onClick={() => setIsSidebarOpen(true)}
               className="lg:hidden p-2 hover:bg-slate-100 rounded-xl transition-colors border-2 border-transparent active:border-slate-900"
             >
                <Menu size={20} />
             </button>
             
             <div className="hidden sm:flex items-center gap-4">
                <span className="text-[10px] font-bold tracking-widest text-[#B8B3AE] uppercase font-['Architects_Daughter']">Agile Cockpit</span>
                <span className="text-slate-200">/</span>
                <span className="text-[10px] font-bold tracking-widest text-rose-500 uppercase italic font-['Architects_Daughter']">Coach Console</span>
             </div>
          </div>
          
          <div className="flex items-center gap-4">
             <div className="flex flex-col items-end hidden xs:block">
                <span className="text-[10px] font-bold text-slate-900 leading-none">Sprint 25</span>
                <span className="text-[9px] text-emerald-500 font-bold uppercase tracking-tighter">Active</span>
             </div>
             <div className="w-10 h-10 rounded-xl border-2 border-slate-900 bg-white flex items-center justify-center text-[12px] font-bold text-slate-900 shadow-[2px_2px_0_rgba(0,0,0,1)]">
                ST
             </div>
          </div>
        </header>
        
        <div className="min-h-[calc(100vh-64px)] w-full">
          <Outlet />
        </div>
        <Toaster position="bottom-right" expand={false} />
      </main>
    </div>
  );
}
