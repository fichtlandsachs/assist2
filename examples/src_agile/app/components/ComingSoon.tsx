import React from 'react';
import { Users, Calendar, Sparkles } from 'lucide-react';

export function Team() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-10 space-y-6">
      <div className="w-24 h-24 bg-blue-100 dark:bg-blue-900 rounded-3xl flex items-center justify-center">
        <Users size={48} className="text-blue-600 dark:text-blue-400" />
      </div>
      <div className="max-w-md">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Team Management</h2>
        <p className="text-slate-500 font-medium">Coming soon: Manage your team members, their roles, and track individual velocity with Karl's AI insights.</p>
      </div>
      <button className="px-6 py-3 bg-blue-600 text-white rounded-xl font-bold hover:bg-blue-500 transition-all flex items-center gap-2">
         <Sparkles size={18} /> Get Notified
      </button>
    </div>
  );
}

export function Planning() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-10 space-y-6">
      <div className="w-24 h-24 bg-orange-100 dark:bg-orange-900 rounded-3xl flex items-center justify-center">
        <Calendar size={48} className="text-orange-600 dark:text-orange-400" />
      </div>
      <div className="max-w-md">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Sprint Planning Facilitator</h2>
        <p className="text-slate-500 font-medium">Karl will soon be able to facilitate your sprint planning, suggesting story points based on historical data and team capacity.</p>
      </div>
       <button className="px-6 py-3 bg-orange-600 text-white rounded-xl font-bold hover:bg-orange-500 transition-all flex items-center gap-2">
         <Sparkles size={18} /> Join Beta
      </button>
    </div>
  );
}
