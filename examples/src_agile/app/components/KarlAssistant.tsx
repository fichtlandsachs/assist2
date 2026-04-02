import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  User, 
  Sparkles, 
  Paperclip, 
  Activity, 
  ChevronRight,
  TrendingDown,
  Info,
  Users,
  PenTool,
  Smile,
  Zap,
  RotateCcw
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import karlSitting from "figma:asset/3ff3b01f376f207a34a2793ac5ebf0b23c858bef.png";
import { ImageWithFallback } from './figma/ImageWithFallback';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: '1',
    role: 'assistant',
    content: "Hi! Ich habe mir euren Sprint-Sketch angesehen. Alles sieht super aus! Die Velocity ist stabil, nur bei den Reviews gibt's einen kleinen Stau. Wie kann ich euch heute unterstützen? ✏️",
    timestamp: new Date(),
  },
];

export function KarlAssistant() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    setTimeout(() => {
      const response: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: getKarlResponse(input),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, response]);
      setIsTyping(false);
    }, 1500);
  };

  const getKarlResponse = (query: string) => {
    const q = query.toLowerCase();
    if (q.includes('sprint') || q.includes('velocity')) {
      return "Analyse fertig! ✏️ Eure Velocity ist mit 64 Punkten echt stabil (+12%!). Das ist spitze! Für den nächsten Sprint würde ich 8 Stories vorschlagen. Sollen wir das direkt so einplanen? 🚀";
    }
    if (q.includes('retro')) {
      return "Oh, Retro-Zeit! 🎨 In der letzten Retro war das Thema 'Fokus' wichtig. Ich hab da mal ein Template vorbereitet, das genau darauf abzielt. Lust auf einen kleinen Sketch dazu? ✨";
    }
    if (q.includes('daily')) {
       return "Daily Check! ✅ Ticket #242 hängt ein bisschen fest. Vielleicht mal kurz bei Dave nachhaken? Ich setze es mal auf die Agenda für morgen, damit wir es nicht vergessen! 📝";
    }
    return "Gute Frage! Ich schau mir das mal im Kontext eures Flows an. Soll ich dazu eine kleine Skizze machen oder eine Analyse erstellen? Ich bin bereit! ✏️✨";
  };

  return (
    <div className="flex h-full max-w-7xl mx-auto w-full p-4 sm:p-8 gap-8 bg-[#fdfaf6] text-slate-800 font-sans relative">
      {/* Background Dots Pattern */}
      <div className="absolute inset-0 opacity-[0.05] pointer-events-none" style={{ backgroundImage: 'radial-gradient(#000 0.5px, transparent 0.5px)', backgroundSize: '25px 25px' }} />

      {/* 1. Left Sidebar: AI Coach Console */}
      <div className="hidden lg:flex flex-col w-64 xl:w-80 shrink-0 space-y-8 relative z-10">
        <div className="bg-white border-2 border-slate-900 p-8 rounded-[2.5rem] shadow-[10px_10px_0_rgba(0,0,0,1)] relative overflow-hidden group rotate-[-1deg]">
          <div className="absolute top-0 right-0 p-4 opacity-5 rotate-12 pointer-events-none group-hover:rotate-45 transition-transform duration-700">
             <PenTool size={100} />
          </div>
          
          <div className="flex flex-col items-center gap-6 mb-10 relative z-10">
            <div className="w-24 h-24 bg-amber-50 border-2 border-slate-900 rounded-3xl flex items-center justify-center p-3 shadow-[4px_4px_0_rgba(0,0,0,1)] relative group-hover:scale-105 transition-transform">
               <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#000_1.5px,transparent_1.5px)] bg-[size:8px_8px]" />
               <ImageWithFallback src={karlSitting} alt="Karl" className="w-full h-full object-contain grayscale brightness-110 contrast-125 group-hover:grayscale-0 transition-all duration-500" />
            </div>
            <div className="text-center">
               <h2 className="text-3xl font-['Gochi_Hand'] text-slate-900 leading-none mb-1">Sketch-Coach</h2>
               <p className="text-[10px] font-bold tracking-[0.2em] text-rose-500 uppercase font-['Architects_Daughter']">Live Feedback</p>
               <div className="flex items-center justify-center gap-2 mt-3 px-3 py-1 bg-emerald-50 border-2 border-slate-900 rounded-full shadow-[2px_2px_0_rgba(0,0,0,1)]">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
                  <span className="text-[9px] font-bold text-slate-600 uppercase tracking-widest font-['Architects_Daughter']">Online</span>
               </div>
            </div>
          </div>

          <div className="space-y-4 relative z-10">
             <CoachMetric label="Flow Score" value="82%" icon={<Activity size={16} />} color="text-rose-500" bg="bg-rose-50" />
             <CoachMetric label="Team Mood" value="High" icon={<Smile size={16} />} color="text-sky-500" bg="bg-sky-50" />
          </div>
        </div>

        {/* Intelligence Feed */}
        <div className="bg-white border-2 border-slate-900 rounded-[2.5rem] p-8 shadow-[6px_6px_0_rgba(0,0,0,1)] rotate-[1deg] relative overflow-hidden">
           <div className="absolute -bottom-4 -left-4 opacity-[0.03] rotate-[-15deg]">
              <Sparkles size={100} />
           </div>
           <h3 className="text-[11px] font-bold tracking-[0.2em] text-slate-400 uppercase mb-8 flex items-center gap-2 font-['Architects_Daughter']">
              <PenTool size={14} className="text-rose-500" /> Live Annotations
           </h3>
           <div className="space-y-6 text-slate-500 relative z-10">
              <IntelligenceItem title="Review Bottleneck" type="warning" />
              <IntelligenceItem title="Daily Notes Ready" type="info" />
              <IntelligenceItem title="Velocity Boost" type="info" />
           </div>
        </div>
      </div>

      {/* 2. Chat Area */}
      <div className="flex-1 flex flex-col bg-white border-2 border-slate-900 rounded-[2.5rem] sm:rounded-[3rem] shadow-[12px_12px_0_rgba(0,0,0,1)] overflow-hidden h-[calc(100vh-160px)] sm:h-[calc(100vh-140px)] relative z-10">
        {/* Header */}
        <div className="p-4 sm:p-6 px-6 sm:px-10 border-b-2 border-slate-900/10 flex items-center justify-between bg-white/50 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="w-2 h-2 bg-rose-500 rounded-full border border-slate-900 shadow-[0_0_5px_#f43f5e]"></div>
            <span className="text-[9px] sm:text-[11px] font-bold tracking-[0.2em] text-slate-400 uppercase font-['Architects_Daughter']">Conversation Sketch</span>
          </div>
          <div className="flex gap-2">
             <button className="p-2 border-2 border-slate-900 rounded-xl hover:bg-slate-50 transition-all shadow-[2px_2px_0_rgba(0,0,0,1)] active:translate-y-[2px] active:shadow-none">
                <RotateCcw size={16} />
             </button>
          </div>
        </div>

        {/* Messages */}
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-6 sm:p-10 space-y-8 sm:space-y-12 scrollbar-hide"
        >
          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`flex gap-3 sm:gap-6 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl border-2 border-slate-900 flex items-center justify-center shrink-0 shadow-[2px_2px_0_rgba(0,0,0,1)] sm:shadow-[3px_3px_0_rgba(0,0,0,1)] overflow-hidden transition-all ${
                  m.role === 'assistant' ? 'bg-amber-50' : 'bg-slate-900'
                }`}>
                  {m.role === 'assistant' ? (
                    <div className="p-1">
                       <ImageWithFallback src={karlSitting} alt="Karl" className="w-full h-full object-contain grayscale brightness-110" />
                    </div>
                  ) : <User size={18} className="text-white" />}
                </div>
                <div className={`max-w-[85%] sm:max-w-[75%] space-y-2 ${m.role === 'user' ? 'text-right' : ''}`}>
                  <div className={`p-4 sm:p-6 border-2 border-slate-900 shadow-[4px_4px_0_rgba(0,0,0,1)] sm:shadow-[6px_6px_0_rgba(0,0,0,1)] ${
                    m.role === 'assistant'
                      ? 'bg-white rounded-tr-3xl rounded-bl-3xl rounded-br-lg text-[14px] sm:text-[15px] font-["Gochi_Hand"] text-slate-800'
                      : 'bg-rose-400 rounded-tl-3xl rounded-br-3xl rounded-bl-lg text-[13px] sm:text-[14px] font-["Architects_Daughter"] font-bold text-white'
                  }`}>
                    <p>{m.content}</p>
                  </div>
                  <span className="text-[8px] font-bold text-slate-400 block px-2 uppercase tracking-widest font-['Architects_Daughter']">
                    {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {isTyping && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3 sm:gap-6">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl bg-amber-50 border-2 border-slate-900 flex items-center justify-center shrink-0 p-1 shadow-[2px_2px_0_rgba(0,0,0,1)]">
                <ImageWithFallback src={karlSitting} alt="Karl" className="w-full h-full object-contain grayscale brightness-110" />
              </div>
              <div className="flex items-center gap-2 p-3 sm:p-4 bg-white border-2 border-slate-900 rounded-tr-2xl rounded-bl-2xl rounded-br-lg shadow-[3px_3px_0_rgba(0,0,0,1)]">
                <span className="w-1 h-1 sm:w-1.5 sm:h-1.5 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                <span className="w-1 h-1 sm:w-1.5 sm:h-1.5 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1 h-1 sm:w-1.5 sm:h-1.5 bg-rose-500 rounded-full animate-bounce"></span>
              </div>
            </motion.div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 sm:p-10 border-t-2 border-slate-900/10 bg-white/50 backdrop-blur-xl sticky bottom-0">
          <div className="relative group">
            <input 
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Frag Karl..."
              className="w-full pl-10 sm:pl-14 pr-16 sm:pr-24 py-3 sm:py-5 bg-white border-2 border-slate-900 rounded-xl sm:rounded-2xl focus:outline-none focus:shadow-[4px_4px_0_rgba(0,0,0,1)] sm:focus:shadow-[6px_6px_0_rgba(0,0,0,1)] text-[12px] sm:text-[14px] font-['Architects_Daughter'] font-bold text-slate-800 placeholder-slate-300 transition-all shadow-[2px_2px_0_rgba(0,0,0,1)] sm:shadow-[4px_4px_0_rgba(0,0,0,1)]"
            />
            <div className="absolute left-4 sm:left-6 top-1/2 -translate-y-1/2 text-rose-500">
               <PenTool size={16} />
            </div>
            <div className="absolute right-4 sm:right-6 top-1/2 -translate-y-1/2 flex gap-2 sm:gap-4">
              <button 
                onClick={handleSend}
                disabled={!input.trim()}
                className={`p-2 sm:p-2.5 rounded-lg sm:rounded-xl border-2 border-slate-900 transition-all ${
                  input.trim() 
                    ? 'bg-slate-900 text-white shadow-[2px_2px_0_rgba(0,0,0,1)]' 
                    : 'text-slate-300 bg-white border-slate-200'
                }`}
              >
                <Send size={16} />
              </button>
            </div>
          </div>
          <div className="flex justify-between items-center mt-4 sm:mt-6 px-2">
             <div className="flex gap-2 sm:gap-4 font-['Architects_Daughter']">
                <QuickPrompt label="Analysis" />
                <QuickPrompt label="Daily" />
             </div>
             <p className="hidden xs:block text-[8px] sm:text-[9px] text-slate-300 font-bold uppercase tracking-[0.3em] font-['Architects_Daughter']">
               v2.5
             </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function CoachMetric({ label, value, icon, color, bg }: { label: string, value: string, icon: React.ReactNode, color: string, bg: string }) {
  return (
    <div className="flex items-center justify-between p-4 bg-white border-2 border-slate-900 rounded-2xl shadow-[4px_4px_0_rgba(0,0,0,1)] group/metric hover:translate-y-[-2px] hover:shadow-[6px_6px_0_rgba(0,0,0,1)] transition-all">
       <div className="flex items-center gap-3">
          <div className={`${bg} ${color} p-2 rounded-lg border-2 border-slate-900/5 transition-colors group-hover/metric:border-slate-900`}>{icon}</div>
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest font-['Architects_Daughter']">{label}</span>
       </div>
       <span className="text-xl font-['Gochi_Hand'] text-slate-900">{value}</span>
    </div>
  );
}

function IntelligenceItem({ title, type }: { title: string, type: 'warning' | 'info' }) {
   return (
      <div className="flex items-center gap-3 font-['Architects_Daughter'] font-bold text-[12px] group cursor-pointer hover:text-slate-900 transition-colors">
         <div className={`w-2 h-2 rounded-full border border-slate-900 ${type === 'warning' ? 'bg-amber-400 shadow-[0_0_5px_#fbbf24]' : 'bg-sky-400 shadow-[0_0_5px_#38bdf8]'}`} />
         {title}
      </div>
   );
}

function QuickPrompt({ label }: { label: string }) {
   return (
      <button className="text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:text-slate-900 transition-all flex items-center gap-2 border-2 border-transparent hover:border-slate-900 px-3 py-1.5 rounded-lg hover:shadow-[2px_2px_0_rgba(0,0,0,1)]">
         <div className="w-1 h-1 rounded-full bg-slate-900" />
         {label}
      </button>
   );
}
