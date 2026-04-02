import React, { useState } from 'react';
import { 
  Plus, 
  MoreVertical, 
  Clock, 
  MessageSquare, 
  Paperclip,
  Search,
  Filter,
  UserCircle2,
  ChevronRight,
  PenTool
} from 'lucide-react';
import { motion } from 'motion/react';

const INITIAL_BOARD_DATA = {
  todo: [
    { id: '1', title: 'OAuth Login implementieren', priority: 'High', team: 'Auth', points: 5, comments: 3, tags: ['feature'], rotate: 'rotate-0' },
    { id: '2', title: 'Design Tokens auf v2 aktualisieren', priority: 'Medium', team: 'Design', points: 3, comments: 0, tags: ['debt'], rotate: 'rotate-0' },
  ],
  inProgress: [
    { id: '4', title: 'User Profil Dashboard', priority: 'Medium', team: 'Core', points: 8, comments: 5, tags: ['feature'], rotate: 'rotate-0' },
  ],
  review: [
    { id: '6', title: 'Dark Mode Theme Implementation', priority: 'Low', team: 'UI', points: 3, comments: 12, tags: ['ui'], rotate: 'rotate-0' },
  ],
  done: [
    { id: '7', title: 'Email Benachrichtigungsservice', priority: 'Medium', team: 'Back-end', points: 5, comments: 4, tags: ['done'], rotate: 'rotate-0' },
  ],
};

export function Board() {
  const [data] = useState(INITIAL_BOARD_DATA);

  return (
    <div className="p-4 sm:p-8 flex flex-col h-full bg-[#fdfaf6] text-slate-900 font-sans relative overflow-hidden">
      {/* Background Grid */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'radial-gradient(#000 0.5px, transparent 0.5px)', backgroundSize: '25px 25px' }} />

      {/* Board Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6 mb-8 sm:mb-10 relative z-10">
        <div>
          <h1 className="text-2xl sm:text-3xl font-['Gochi_Hand'] mb-1 sm:mb-2 text-center sm:text-left">Sprint 25 Board ✏️</h1>
          <p className="text-[9px] sm:text-[11px] font-bold tracking-[0.2em] text-slate-400 uppercase font-['Architects_Daughter'] text-center sm:text-left">Ziel: User Authentication MVP</p>
        </div>
        
        <div className="flex flex-col xs:flex-row items-center gap-3 sm:gap-4 w-full sm:w-auto">
          <div className="relative group w-full xs:w-auto">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
            <input 
              type="text" 
              placeholder="Suchen..." 
              className="w-full xs:w-48 pl-10 pr-6 py-2 bg-white border-2 border-slate-900 rounded-xl text-[12px] font-bold font-['Architects_Daughter'] focus:outline-none shadow-[3px_3px_0_rgba(0,0,0,1)] transition-all"
            />
          </div>
          <button className="w-full xs:w-auto flex items-center justify-center gap-2 px-6 py-2 bg-slate-900 text-white text-[11px] font-bold tracking-[0.2em] uppercase rounded-xl shadow-[4px_4px_0_rgba(0,0,0,1)] hover:translate-y-[-2px] hover:shadow-[6px_6px_0_rgba(0,0,0,1)] transition-all active:translate-y-[2px] active:shadow-none">
            <Plus size={14} />
            <span>Neu</span>
          </button>
        </div>
      </div>

      {/* Columns Container */}
      <div className="flex-1 overflow-x-auto pb-6 scrollbar-hide relative z-10 -mx-4 px-4 sm:mx-0 sm:px-0">
        <div className="flex gap-4 sm:gap-8 h-full min-w-max">
          <Column title="TO DO" count={data.todo.length} cards={data.todo} color="bg-rose-400" />
          <Column title="IN ARBEIT" count={data.inProgress.length} cards={data.inProgress} color="bg-amber-400" />
          <Column title="REVIEW" count={data.review.length} cards={data.review} color="bg-sky-400" />
          <Column title="FERTIG" count={data.done.length} cards={data.done} color="bg-emerald-400" />
        </div>
      </div>
    </div>
  );
}

function Column({ title, count, cards, color }: any) {
  return (
    <div className="flex flex-col w-72 shrink-0">
      <div className="flex items-center justify-between mb-6 pb-3 border-b-2 border-slate-900/10">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full border-2 border-slate-900 ${color}`}></div>
          <h3 className="text-[11px] font-bold tracking-[0.2em] text-slate-900 uppercase font-['Architects_Daughter']">{title}</h3>
          <span className="text-[12px] font-['Gochi_Hand'] text-slate-400">({count})</span>
        </div>
        <button className="text-slate-400 hover:text-slate-900 transition-colors">
          <MoreVertical size={14} />
        </button>
      </div>
      
      <div className="flex-1 space-y-6 overflow-y-auto pr-2 scrollbar-hide">
        {cards.map((card: any) => (
          <Card key={card.id} card={card} color={color} />
        ))}
        <button className="w-full py-4 border-2 border-dashed border-slate-900/20 bg-white/50 text-slate-400 hover:border-slate-900 hover:text-slate-900 rounded-2xl transition-all flex items-center justify-center gap-2 text-[10px] font-bold tracking-[0.2em] uppercase font-['Architects_Daughter']">
           <Plus size={14} /> Karte skizzieren
        </button>
      </div>
    </div>
  );
}

function Card({ card, color }: any) {
  return (
    <motion.div 
      whileHover={{ y: -4, rotate: 0 }}
      className={`bg-white p-5 border-2 border-slate-900 rounded-2xl ${card.rotate} shadow-[4px_4px_0_rgba(0,0,0,1)] hover:shadow-[8px_8px_0_rgba(0,0,0,1)] transition-all group cursor-pointer relative overflow-hidden`}
    >
      <div className={`absolute top-0 left-0 w-full h-1 ${color} border-b-2 border-slate-900`} />
      
      <div className="flex justify-between items-start mb-3 mt-2">
        <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-slate-400 font-['Architects_Daughter'] group-hover:text-slate-900 transition-colors">
          {card.priority}
        </span>
        <div className="w-5 h-5 rounded border-2 border-slate-900 bg-slate-50 flex items-center justify-center text-[10px] font-bold font-['Architects_Daughter']">
           {card.team[0]}
        </div>
      </div>
      
      <h4 className="text-[15px] font-['Gochi_Hand'] text-slate-800 leading-tight mb-4">
        {card.title}
      </h4>

      <div className="flex items-center justify-between border-t-2 border-dashed border-slate-100 pt-3">
        <div className="flex items-center gap-3 text-slate-400 font-['Architects_Daughter']">
          <div className="flex items-center gap-1">
             <MessageSquare size={12} />
             <span className="text-[10px] font-bold">{card.comments}</span>
          </div>
        </div>
        <div className="flex items-center gap-1 px-2 py-0.5 border-2 border-slate-900 rounded-lg bg-slate-50 text-slate-900 font-bold font-['Architects_Daughter'] text-[10px]">
           <Clock size={10} />
           <span>{card.points} PTS</span>
        </div>
      </div>
    </motion.div>
  );
}
