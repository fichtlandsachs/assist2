import React from 'react';
import { NavLink } from 'react-router';
import { 
  LayoutDashboard, 
  Cpu, 
  Layers,
  RotateCcw,
  Calendar,
  Settings,
  Zap,
  Activity,
  ChevronRight,
  Sparkles,
  Heart,
  Smile,
  PenTool,
  X
} from 'lucide-react';
import { motion } from 'motion/react';
import { ImageWithFallback } from './figma/ImageWithFallback';
import karlSitting from "figma:asset/3ff3b01f376f207a34a2793ac5ebf0b23c858bef.png";

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/', color: 'text-rose-500', bg: 'bg-rose-50' },
    { icon: Layers, label: 'Backlog', path: '/board', color: 'text-amber-500', bg: 'bg-amber-50' },
    { icon: RotateCcw, label: 'Retros', path: '/retro', color: 'text-indigo-500', bg: 'bg-indigo-50' },
  ];

  return (
    <div className="w-64 h-full bg-[#fdfaf6] border-r-2 border-slate-900/10 flex flex-col font-sans shrink-0 relative z-30 shadow-[4px_0_0_rgba(0,0,0,0.02)]">
      {/* Brand Section */}
      <div className="p-8 pb-10 flex flex-col items-center gap-2 relative">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 lg:hidden p-2 text-slate-400 hover:text-slate-900"
        >
           <X size={20} />
        </button>
        <motion.div 
          whileHover={{ rotate: [-2, 2, -2] }}
          className="w-16 h-16 bg-white border-2 border-slate-900 rounded-xl flex items-center justify-center text-slate-900 shadow-[4px_4px_0_rgba(0,0,0,1)] relative overflow-hidden"
        >
          <div className="absolute -top-1 -left-1 opacity-20">
             <PenTool size={40} />
          </div>
          <Smile size={32} />
        </motion.div>
        <div className="text-center mt-2">
          <span className="font-['Gochi_Hand'] text-3xl text-slate-900 tracking-tight block leading-none">Karl</span>
          <span className="text-[10px] font-bold tracking-[0.2em] text-slate-400 uppercase">the sketch-coach</span>
        </div>
      </div>

      <nav className="flex-1 px-4 overflow-y-auto scrollbar-hide space-y-2 relative z-10">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center justify-between px-4 py-3 transition-all rounded-xl group relative border-2 ${
                isActive 
                  ? 'bg-white border-slate-900 text-slate-900 shadow-[4px_4px_0_rgba(0,0,0,1)] -translate-y-0.5' 
                  : 'border-transparent hover:border-slate-900/20 text-slate-500'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <div className="flex items-center gap-4">
                  <div className={`transition-all ${isActive ? item.color : 'text-slate-400'}`}>
                    <item.icon size={18} strokeWidth={2.5} />
                  </div>
                  <span className={`font-['Architects_Daughter'] font-bold text-[14px] ${isActive ? 'text-slate-900' : 'text-slate-500'}`}>{item.label}</span>
                </div>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Karl Mini-Widget at Bottom */}
      <div className="p-6 m-4 bg-white border-2 border-slate-900 rounded-3xl relative group overflow-hidden shadow-[6px_6px_0_rgba(0,0,0,1)] hover:shadow-[8px_8px_0_rgba(0,0,0,1)] transition-all">
        <div className="absolute inset-0 bg-amber-50/30 opacity-0 group-hover:opacity-100 transition-opacity" />
        <div className="absolute -right-4 -top-4 opacity-5 pointer-events-none group-hover:rotate-12 transition-transform">
           <PenTool size={80} className="rotate-45" />
        </div>
        
        <div className="flex flex-col items-center gap-4 relative z-10 text-center">
           <motion.div 
             whileHover={{ scale: 1.1, rotate: [0, -5, 5, 0] }}
             className="w-20 h-20 bg-amber-50 border-2 border-slate-900 rounded-2xl flex items-center justify-center p-2 relative shadow-[4px_4px_0_rgba(0,0,0,0.1)]"
           >
              <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#000_1px,transparent_1px)] bg-[size:5px_5px]" />
              <ImageWithFallback 
                src={karlSitting} 
                alt="Karl" 
                className="w-full h-full object-contain grayscale brightness-110 contrast-125 group-hover:grayscale-0 transition-all duration-500"
              />
              <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 border-2 border-slate-900 rounded-full shadow-[2px_2px_0_rgba(0,0,0,1)]" />
           </motion.div>
           
           <div className="space-y-1">
              <p className="text-[10px] font-bold tracking-[0.15em] text-slate-400 uppercase font-['Architects_Daughter'] flex items-center justify-center gap-1">
                 <Sparkles size={10} className="text-amber-500" /> Karl is thinking...
              </p>
              <p className="text-[16px] font-['Gochi_Hand'] text-slate-800 leading-tight">"Lets sketch success together!"</p>
           </div>
        </div>
        
        <NavLink 
          to="/chat" 
          onClick={onClose}
          className="w-full mt-5 py-3 bg-slate-900 text-white text-[11px] font-bold tracking-[0.2em] uppercase rounded-xl transition-all hover:bg-rose-500 active:scale-95 flex items-center justify-center gap-2 shadow-[3px_3px_0_rgba(255,255,255,0.1)]"
        >
           <Cpu size={14} /> Talk to Karl
        </NavLink>
      </div>
    </div>
  );
}
