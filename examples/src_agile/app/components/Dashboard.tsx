import React from 'react';
import { 
  ArrowUpRight,
  Target,
  Clock,
  Zap,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Sparkles,
  Activity,
  ChevronRight,
  Smile,
  PenTool,
  Heart,
  Hash
} from 'lucide-react';
import { motion } from 'motion/react';
import { ImageWithFallback } from './figma/ImageWithFallback';
import karlSitting from "figma:asset/3ff3b01f376f207a34a2793ac5ebf0b23c858bef.png";
import { BurndownChart, VelocityChart } from './AgileCharts';

export function Dashboard() {
  const sprintStats = [
    { label: 'Sprint Day', value: '08/10', icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50', rotate: 'rotate-0' },
    { label: 'Scope', value: '+4 Pkt', icon: AlertCircle, color: 'text-orange-600', bg: 'bg-orange-50', rotate: 'rotate-0' },
    { label: 'Done', value: '62%', icon: CheckCircle2, color: 'text-rose-600', bg: 'bg-rose-50', rotate: 'rotate-0' },
    { label: 'Blockers', value: '02', icon: Zap, color: 'text-sky-600', bg: 'bg-sky-50', rotate: 'rotate-0' },
  ];

  return (
    <div className="p-4 sm:p-8 min-h-screen font-sans text-slate-900 bg-[#fdfaf6] relative overflow-hidden">
      {/* Sketchnote Grid Background */}
      <div className="absolute inset-0 opacity-[0.05] pointer-events-none" style={{ backgroundImage: 'radial-gradient(#000 0.5px, transparent 0.5px)', backgroundSize: '30px 30px' }} />

      <div className="relative z-10 max-w-6xl mx-auto">
        {/* Header with Karl Hero */}
        <div className="mb-8 sm:mb-12 relative">
          <div className="flex flex-col lg:flex-row items-center gap-6 sm:gap-10 bg-white border-2 border-slate-900 p-6 sm:p-8 rounded-[2rem] sm:rounded-3xl shadow-[6px_6px_0_rgba(0,0,0,1)] sm:shadow-[8px_8px_0_rgba(0,0,0,1)] relative overflow-hidden">
             {/* Decorative Elements */}
             <div className="absolute top-0 right-0 p-4 opacity-5 sm:opacity-10 rotate-12 pointer-events-none">
                <PenTool size={120} />
             </div>
             
             {/* Karl Large Illustration */}
             <motion.div 
               initial={{ x: -20, opacity: 0 }}
               animate={{ x: 0, opacity: 1 }}
               className="relative shrink-0 w-full sm:w-auto flex justify-center lg:block"
             >
                <div className="w-32 h-32 sm:w-48 sm:h-48 bg-amber-50 border-2 border-slate-900 rounded-[2rem] sm:rounded-[2.5rem] flex items-center justify-center p-3 sm:p-4 relative shadow-[4px_4px_0_rgba(0,0,0,0.1)] group transition-transform hover:scale-105">
                   <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#000_2px,transparent_2px)] bg-[size:10px_10px]" />
                   <ImageWithFallback 
                     src={karlSitting} 
                     alt="Karl" 
                     className="w-full h-full object-contain grayscale brightness-110 contrast-125 transition-all group-hover:grayscale-0 group-hover:brightness-100 group-hover:contrast-100"
                   />
                   {/* Online Pulse */}
                   <div className="absolute -top-2 -right-2 sm:top-4 sm:right-4 flex items-center gap-2 px-2 sm:px-3 py-1 bg-emerald-500 text-white rounded-full border-2 border-slate-900 shadow-[2px_2px_0_rgba(0,0,0,1)] text-[8px] sm:text-[10px] font-bold uppercase tracking-widest">
                      <div className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                      Live
                   </div>
                </div>
                {/* Hand-drawn Annotation */}
                <div className="absolute -bottom-2 sm:-bottom-4 -right-2 sm:-right-8 bg-white border-2 border-slate-900 px-3 py-1 sm:px-4 sm:py-2 rounded-xl shadow-[3px_3px_0_rgba(0,0,0,1)] rotate-3">
                   <span className="text-[10px] sm:text-[12px] font-bold text-slate-800 font-['Architects_Daughter']">"Hi, I'm Karl!" 👋</span>
                </div>
             </motion.div>

             <div className="flex-1 space-y-4 sm:space-y-6 text-center lg:text-left">
                <div className="space-y-1 sm:space-y-2">
                   <div className="flex items-center justify-center lg:justify-start gap-3">
                      <span className="text-[10px] sm:text-[12px] font-bold tracking-[0.2em] text-rose-500 uppercase flex items-center gap-2 font-['Architects_Daughter']">
                         Sprint 25 Status
                      </span>
                      <div className="hidden sm:block h-0.5 w-12 bg-slate-200" />
                   </div>
                   <h1 className="text-3xl sm:text-5xl font-black text-slate-900 leading-tight">
                      Guten Morgen, <span className="text-rose-500">Team!</span> 
                   </h1>
                </div>

                <div className="relative px-4 sm:px-0">
                   <div className="hidden sm:block absolute -left-6 top-2 text-rose-300 opacity-50">
                      <Sparkles size={24} />
                   </div>
                   <p className="text-lg sm:text-2xl font-['Gochi_Hand'] text-slate-700 leading-relaxed max-w-xl mx-auto lg:mx-0">
                      "Ich habe eure Velocity gecheckt – sieht super aus! <span className="underline decoration-wavy decoration-rose-300 underline-offset-4">Heute</span> fokussieren wir uns auf die Core-Features, okay?"
                   </p>
                </div>

                <div className="flex flex-wrap justify-center lg:justify-start gap-3 sm:gap-4 pt-2">
                   <div className="flex items-center gap-2 px-3 py-1.5 sm:px-4 sm:py-2 bg-slate-50 border-2 border-slate-900 rounded-xl shadow-[3px_3px_0_rgba(0,0,0,1)]">
                      <Target size={14} className="text-amber-500" />
                      <span className="text-[9px] sm:text-[11px] font-bold text-slate-600 uppercase font-['Architects_Daughter']">MVP Core Delivery</span>
                   </div>
                   <div className="flex items-center gap-2 px-3 py-1.5 sm:px-4 sm:py-2 bg-white border-2 border-slate-900 rounded-xl shadow-[3px_3px_0_rgba(0,0,0,1)]">
                      <Smile size={14} className="text-sky-500" />
                      <span className="text-[9px] sm:text-[11px] font-bold text-slate-600 uppercase font-['Architects_Daughter']">Mood: Energetic</span>
                   </div>
                </div>
             </div>
          </div>
        </div>

        {/* 2. Key Metrics Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          {sprintStats.map((stat) => (
            <motion.div 
              key={stat.label} 
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className={`bg-white border-2 border-slate-900 p-5 rounded-2xl ${stat.rotate} shadow-[4px_4px_0_rgba(0,0,0,1)] group hover:-translate-y-1 hover:shadow-[6px_6px_0_rgba(0,0,0,1)] transition-all`}
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`p-2 rounded-lg ${stat.bg} ${stat.color} border-2 border-slate-900/5`}>
                  <stat.icon size={20} />
                </div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest font-['Architects_Daughter']">{stat.label}</span>
              </div>
              <div className="text-3xl font-bold tracking-tight text-slate-900 group-hover:text-rose-500 transition-colors">{stat.value}</div>
            </motion.div>
          ))}
        </div>

        {/* 3. Main Hub */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
          
          <div className="lg:col-span-2 space-y-6 sm:space-y-8">
            <section className="bg-white border-2 border-slate-900 p-6 sm:p-8 rounded-[2rem] sm:rounded-3xl shadow-[6px_6px_0_rgba(0,0,0,1)] relative overflow-hidden group">
               <div className="absolute top-2 right-4 opacity-[0.03] rotate-12 pointer-events-none">
                  <Activity size={120} />
               </div>
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
                <div className="flex items-center gap-3">
                  <PenTool size={20} className="text-rose-500" />
                  <h2 className="text-[10px] sm:text-[12px] font-bold tracking-[0.2em] text-slate-800 uppercase font-['Architects_Daughter']">Burndown Pulse</h2>
                </div>
                <div className="flex items-center gap-4 sm:gap-6">
                   <div className="flex items-center gap-2">
                      <div className="w-3 h-3 border-2 border-slate-900 bg-black rounded-full" />
                      <span className="text-[9px] sm:text-[10px] font-bold text-slate-500 uppercase font-['Architects_Daughter']">Real</span>
                   </div>
                   <div className="flex items-center gap-2 opacity-30">
                      <div className="w-3 h-3 border-2 border-slate-900 bg-white rounded-full" />
                      <span className="text-[9px] sm:text-[10px] font-bold text-slate-500 uppercase font-['Architects_Daughter']">Plan</span>
                   </div>
                </div>
              </div>
              <div className="h-[200px] sm:h-[250px]">
                <BurndownChart />
              </div>
            </section>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8">
               <section className="bg-white border-2 border-slate-900 p-6 sm:p-8 rounded-[2rem] sm:rounded-3xl shadow-[6px_6px_0_rgba(0,0,0,1)]">
                  <div className="flex items-center gap-3 mb-6">
                     <Smile size={20} className="text-sky-500" />
                     <h2 className="text-[10px] sm:text-[12px] font-bold tracking-[0.2em] text-slate-800 uppercase font-['Architects_Daughter']">Flow Health</h2>
                  </div>
                  <div className="space-y-6">
                     <ProgressItem label="Building" current={6} total={10} color="bg-rose-400" />
                     <ProgressItem label="Testing" current={4} total={10} color="bg-amber-400" />
                  </div>
               </section>

               <section className="bg-rose-400 border-2 border-slate-900 p-6 sm:p-8 rounded-[2rem] sm:rounded-3xl relative overflow-hidden group shadow-[6px_6px_0_rgba(0,0,0,1)]">
                  <div className="absolute -top-4 -right-4 opacity-10 rotate-[-15deg]">
                     <Zap size={80} fill="black" />
                  </div>
                  <h3 className="text-[10px] sm:text-[12px] font-bold tracking-[0.2em] text-white uppercase mb-4 font-['Architects_Daughter']">Karls Insight</h3>
                  <p className="text-[16px] sm:text-[18px] font-['Gochi_Hand'] text-white mb-6 leading-tight">
                    &quot;Looking good! But Ticket #402 is stuck for 2 days. Lets talk about it!&quot;
                  </p>
                  <button className="w-full sm:w-auto flex items-center justify-center gap-2 text-[10px] font-bold text-slate-900 uppercase bg-white px-5 py-3 rounded-xl border-2 border-slate-900 shadow-[3px_3px_0_rgba(0,0,0,1)] hover:translate-y-[-2px] transition-all active:translate-y-[2px] active:shadow-none">
                     Help Me <ArrowUpRight size={14} />
                  </button>
               </section>
            </div>
          </div>

          <div className="space-y-6 sm:space-y-8">
            <section className="bg-white border-2 border-slate-900 p-6 sm:p-8 rounded-[2rem] sm:rounded-3xl relative overflow-hidden shadow-[6px_6px_0_rgba(0,0,0,1)]">
              <div className="flex items-center justify-between mb-8">
                 <h3 className="text-[10px] sm:text-[12px] font-bold tracking-[0.2em] text-slate-800 uppercase font-['Architects_Daughter']">Velocity Hub</h3>
                 <div className="text-emerald-600 text-[10px] font-bold flex items-center gap-1 font-['Architects_Daughter'] underline">
                    +12% <TrendingUp size={12} />
                 </div>
              </div>
              <div className="h-[120px] sm:h-[140px]">
                <VelocityChart />
              </div>
              <div className="mt-8 pt-8 border-t-2 border-dashed border-slate-200 flex justify-between items-end">
                 <div>
                    <div className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">64.2</div>
                    <div className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase font-['Architects_Daughter']">History Score</div>
                 </div>
                 <div className="w-10 h-10 border-2 border-slate-900 rounded-lg flex items-center justify-center text-rose-500 shadow-[2px_2px_0_rgba(0,0,0,1)]">
                    <Heart size={20} fill="currentColor" />
                 </div>
              </div>
            </section>

            <section className="bg-slate-900 p-8 rounded-3xl shadow-[6px_6px_0_rgba(0,0,0,1)] relative overflow-hidden group">
               <div className="absolute top-0 left-0 w-full h-1 bg-rose-500" />
               <div className="flex items-center gap-2 mb-8 text-white/40">
                  <Hash size={14} />
                  <h3 className="text-[10px] font-bold tracking-[0.2em] uppercase font-['Architects_Daughter']">Quick Actions</h3>
               </div>
               <div className="space-y-3">
                  <ActionLink label="Generate Daily 📝" color="text-rose-400" />
                  <ActionLink label="Team Health Check 🩺" color="text-amber-400" />
               </div>
            </section>
          </div>

        </div>
      </div>
    </div>
  );
}

function ProgressItem({ label, current, total, color }: any) {
  const width = (current / total) * 100;
  return (
    <div className="space-y-2">
       <div className="flex justify-between items-center text-[11px] font-bold uppercase font-['Architects_Daughter']">
          <span className="text-slate-400">{label}</span>
          <span className="text-slate-900 underline decoration-dotted">{current} / {total}</span>
       </div>
       <div className="h-4 w-full bg-slate-50 border-2 border-slate-900 rounded-full overflow-hidden p-0.5">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${width}%` }}
            transition={{ duration: 1.5 }}
            className={`h-full ${color} border-r-2 border-slate-900 rounded-full shadow-inner`}
          />
       </div>
    </div>
  );
}

function ActionLink({ label, color }: any) {
   return (
      <button className="w-full flex items-center justify-between p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-all border-2 border-transparent hover:border-white/10 group">
         <span className={`text-[12px] font-bold font-['Architects_Daughter'] ${color}`}>{label}</span>
         <ChevronRight size={14} className="text-white/20 group-hover:text-white transition-colors" />
      </button>
   );
}
