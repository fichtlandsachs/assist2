import React, { useState } from 'react';
import { 
  Plus, 
  ThumbsUp, 
  ThumbsDown, 
  Lightbulb, 
  ArrowRight,
  Share2,
  Download,
  Calendar,
  MoreVertical,
  PenTool,
  Send
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import confetti from 'canvas-confetti';

interface RetroItem {
  id: string;
  content: string;
  votes: number;
  author: string;
  rotate: string;
}

export function Retrospective() {
  const [items, setItems] = useState({
    good: [
      { id: '1', content: 'Die Team-Kommunikation hat sich deutlich verbessert.', votes: 5, author: 'Alice', rotate: 'rotate-[1deg]' },
      { id: '2', content: 'Die neue CI/CD-Pipeline spart uns Stunden!', votes: 8, author: 'Bob', rotate: 'rotate-[-1deg]' },
    ],
    bad: [
      { id: '3', content: 'Design-Handoff ist immer noch unklar.', votes: 3, author: 'Charlie', rotate: 'rotate-[2deg]' },
      { id: '4', content: 'Zu viele Meetings während der Fokus-Zeit.', votes: 12, author: 'Dave', rotate: 'rotate-[-2deg]' },
    ],
    ideas: [
      { id: '5', content: 'Einführung eines "No Meeting Wednesdays".', votes: 15, author: 'Eve', rotate: 'rotate-[1deg]' },
    ],
  });

  const [input, setInput] = useState({ column: '', value: '' });

  const addVote = (column: keyof typeof items, id: string) => {
    setItems((prev) => ({
      ...prev,
      [column]: prev[column].map((item) => 
        item.id === id ? { ...item, votes: item.votes + 1 } : item
      ),
    }));
    confetti({
      particleCount: 20,
      spread: 50,
      origin: { y: 0.8 },
      colors: ['#000', '#f43f5e', '#fbbf24']
    });
  };

  const addItem = (column: keyof typeof items) => {
    if (!input.value.trim()) return;
    const newItem = {
      id: Date.now().toString(),
      content: input.value,
      votes: 0,
      author: 'Ich',
      rotate: (Math.random() > 0.5 ? 'rotate-[1deg]' : 'rotate-[-1deg]')
    };
    setItems((prev) => ({
      ...prev,
      [column]: [...prev[column], newItem],
    }));
    setInput({ column: '', value: '' });
  };

  return (
    <div className="p-4 sm:p-8 max-w-7xl mx-auto w-full font-sans text-slate-900 bg-[#fdfaf6] relative min-h-screen">
      {/* Sketchnote Grid Background */}
      <div className="absolute inset-0 opacity-[0.05] pointer-events-none" style={{ backgroundImage: 'radial-gradient(#000 0.5px, transparent 0.5px)', backgroundSize: '30px 30px' }} />

      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-10 sm:mb-14 relative z-10">
        <div>
          <div className="flex items-center gap-3 mb-3 uppercase tracking-[0.2em] font-bold text-slate-400 text-[10px] font-['Architects_Daughter']">
            <Calendar size={12} className="text-rose-500" />
            <span>20. März 2026</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-['Gochi_Hand'] mb-2">Retro Sprint 24 ✏️</h1>
          <div className="relative inline-block">
            <p className="text-[11px] sm:text-[13px] font-bold text-slate-600 italic font-['Architects_Daughter'] bg-amber-50 px-3 py-1 border-2 border-slate-900 shadow-[3px_3px_0_rgba(0,0,0,1)] rotate-[-1deg]">
              &quot;Offenheit ist die Basis für Wachstum.&quot;
            </p>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-3 sm:gap-4 w-full md:w-auto">
          <button className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-2 border-2 border-slate-900 bg-white text-slate-900 text-[11px] font-bold tracking-[0.1em] uppercase rounded-xl shadow-[4px_4px_0_rgba(0,0,0,1)] hover:translate-y-[-2px] hover:shadow-[6px_6px_0_rgba(0,0,0,1)] transition-all">
            <Download size={14} />
            <span className="hidden sm:inline">Export</span>
          </button>
          <button className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-2 bg-slate-900 text-white text-[11px] font-bold tracking-[0.2em] uppercase rounded-xl shadow-[4px_4px_0_rgba(0,0,0,1)] hover:translate-y-[-2px] hover:shadow-[6px_6px_0_rgba(0,0,0,1)] transition-all active:translate-y-[2px] active:shadow-none">
            <Share2 size={14} />
            <span>Teilen</span>
          </button>
        </div>
      </div>

      {/* Retro Board */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 sm:gap-12 relative z-10">
        <RetroColumn 
          title="WAS LIEF GUT?" 
          icon={<ThumbsUp size={16} />}
          items={items.good}
          color="bg-emerald-400"
          onVote={(id) => addVote('good', id)}
          onAdd={() => setInput({ column: 'good', value: '' })}
          activeAdd={input.column === 'good'}
          inputValue={input.value}
          onInputChange={(v) => setInput({ ...input, value: v })}
          onSave={() => addItem('good')}
        />
        <RetroColumn 
          title="WAS FEHLTE?" 
          icon={<ThumbsDown size={16} />}
          items={items.bad}
          color="bg-rose-400"
          onVote={(id) => addVote('bad', id)}
          onAdd={() => setInput({ column: 'bad', value: '' })}
          activeAdd={input.column === 'bad'}
          inputValue={input.value}
          onInputChange={(v) => setInput({ ...input, value: v })}
          onSave={() => addItem('bad')}
        />
        <RetroColumn 
          title="NEUE IDEEN" 
          icon={<Lightbulb size={16} />}
          items={items.ideas}
          color="bg-amber-400"
          onVote={(id) => addVote('ideas', id)}
          onAdd={() => setInput({ column: 'ideas', value: '' })}
          activeAdd={input.column === 'ideas'}
          inputValue={input.value}
          onInputChange={(v) => setInput({ ...input, value: v })}
          onSave={() => addItem('ideas')}
        />
      </div>
    </div>
  );
}

function RetroColumn({ title, icon, items, color, onVote, onAdd, activeAdd, inputValue, onInputChange, onSave }: any) {
  return (
    <div className="flex flex-col min-h-[400px] sm:min-h-[600px]">
      <div className="flex items-center justify-between py-4 mb-8 border-b-2 border-slate-900/10 group cursor-pointer">
        <div className="flex items-center gap-3">
           <div className={`w-4 h-4 rounded-full border-2 border-slate-900 shadow-[2px_2px_0_rgba(0,0,0,1)] ${color}`}></div>
           <h3 className="text-[12px] font-bold tracking-[0.2em] text-slate-900 uppercase font-['Architects_Daughter']">{title}</h3>
        </div>
        <button 
          onClick={onAdd}
          className="p-2 border-2 border-slate-900 rounded-lg bg-white shadow-[2px_2px_0_rgba(0,0,0,1)] hover:bg-slate-50 transition-all hover:translate-y-[-1px] active:translate-y-[1px] active:shadow-none"
        >
          <Plus size={16} className="text-slate-900" />
        </button>
      </div>

      <div className="flex-1 space-y-8 overflow-y-auto pr-2 scrollbar-hide">
        <AnimatePresence mode="popLayout">
          {activeAdd && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.9, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 10 }}
              className="p-6 bg-white border-2 border-slate-900 shadow-[6px_6px_0_rgba(0,0,0,1)] rounded-2xl mb-8 relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 w-full h-1 bg-slate-900" />
              <textarea 
                value={inputValue}
                onChange={(e) => onInputChange(e.target.value)}
                autoFocus
                placeholder="Deine Notiz skizzieren..."
                className="w-full bg-transparent border-none focus:outline-none resize-none text-[16px] sm:text-[18px] font-['Gochi_Hand'] text-slate-800 min-h-[120px] scrollbar-hide"
              />
              <div className="flex justify-end pt-4 border-t-2 border-dashed border-slate-100 mt-2">
                 <button 
                  onClick={onSave}
                  className="px-6 py-2 bg-slate-900 text-white text-[10px] font-bold tracking-[0.2em] uppercase rounded-xl shadow-[4px_4px_0_rgba(0,0,0,1)] hover:translate-y-[-2px] hover:shadow-[6px_6px_0_rgba(0,0,0,1)] transition-all flex items-center gap-2"
                >
                  <Send size={14} />
                  <span>Posten</span>
                </button>
              </div>
            </motion.div>
          )}

          {items.map((item: any) => (
            <motion.div 
              key={item.id}
              layout
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className={`p-6 bg-white border-2 border-slate-900 shadow-[8px_8px_0_rgba(0,0,0,1)] rounded-3xl group transition-all ${item.rotate} hover:rotate-0 hover:shadow-[12px_12px_0_rgba(0,0,0,1)] cursor-default relative overflow-hidden`}
            >
              <div className={`absolute top-0 left-0 w-full h-1.5 ${color} border-b-2 border-slate-900`} />
              
              <div className="absolute top-4 right-4 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity pointer-events-none">
                <PenTool size={60} className="rotate-12" />
              </div>
              
              <p className="text-[18px] sm:text-[20px] font-['Gochi_Hand'] text-slate-800 leading-tight mb-8 relative z-10">
                &quot;{item.content}&quot;
              </p>
              
              <div className="flex items-center justify-between border-t-2 border-dashed border-slate-100 pt-5 relative z-10">
                <div className="flex items-center gap-3">
                   <div className="w-8 h-8 rounded-xl bg-slate-50 border-2 border-slate-900 flex items-center justify-center shadow-[2px_2px_0_rgba(0,0,0,1)] overflow-hidden">
                      <div className="text-[11px] font-bold font-['Architects_Daughter'] text-slate-900">{item.author[0]}</div>
                   </div>
                   <span className="text-[10px] text-slate-400 font-bold uppercase tracking-[0.15em] font-['Architects_Daughter']">{item.author}</span>
                </div>
                <button 
                  onClick={() => onVote(item.id)}
                  className="flex items-center gap-2 px-4 py-2 border-2 border-slate-900 rounded-xl bg-white hover:bg-rose-50 transition-all shadow-[3px_3px_0_rgba(0,0,0,1)] active:translate-y-[2px] active:shadow-none hover:translate-y-[-1px]"
                >
                  <ThumbsUp size={14} className="text-rose-500 fill-rose-500/10" />
                  <span className="text-[14px] font-bold font-['Gochi_Hand'] text-slate-900">{item.votes}</span>
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
