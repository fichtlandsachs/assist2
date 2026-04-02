import React from 'react';
import { 
  ComposedChart,
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Area,
  BarChart,
  Bar,
  Cell
} from 'recharts';

const burndownData = [
  { day: 'T1', remaining: 80, ideal: 80 },
  { day: 'T2', remaining: 75, ideal: 70 },
  { day: 'T3', remaining: 65, ideal: 60 },
  { day: 'T4', remaining: 62, ideal: 50 },
  { day: 'T5', remaining: 45, ideal: 40 },
  { day: 'T6', remaining: 30, ideal: 30 },
  { day: 'T7', remaining: 25, ideal: 20 },
  { day: 'T8', remaining: 10, ideal: 10 },
  { day: 'T9', remaining: 5, ideal: 0 },
];

const velocityData = [
  { sprint: 'S20', points: 45 },
  { sprint: 'S21', points: 52 },
  { sprint: 'S22', points: 48 },
  { sprint: 'S23', points: 61 },
  { sprint: 'S24', points: 58 },
  { sprint: 'S25', points: 64 },
];

export function BurndownChart() {
  return (
    <div className="h-[250px] w-full mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart id="burndown-chart-main" data={burndownData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs key="chart-defs">
            <linearGradient id="colorSketch" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#000" stopOpacity={0.05}/>
              <stop offset="95%" stopColor="#000" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid key="grid" strokeDasharray="10 10" vertical={false} stroke="rgba(0,0,0,0.1)" />
          <XAxis 
            key="xaxis"
            dataKey="day" 
            axisLine={{ stroke: '#000', strokeWidth: 2 }} 
            tickLine={false} 
            tick={{ fontSize: 13, fill: '#64748b', fontWeight: 800, fontFamily: 'Architects Daughter' }}
          />
          <YAxis 
            key="yaxis"
            axisLine={{ stroke: '#000', strokeWidth: 2 }} 
            tickLine={false} 
            tick={{ fontSize: 13, fill: '#64748b', fontWeight: 800, fontFamily: 'Architects Daughter' }}
          />
          <Tooltip 
            key="tooltip"
            contentStyle={{ 
              borderRadius: '12px', 
              border: '2px solid #000', 
              fontSize: '14px', 
              backgroundColor: 'white',
              boxShadow: '4px 4px 0 rgba(0,0,0,1)',
              fontFamily: 'Architects Daughter'
            }}
          />
          <Area 
            key="area-data"
            type="monotone" 
            dataKey="remaining" 
            stroke="#000" 
            strokeWidth={3}
            fillOpacity={1} 
            fill="url(#colorSketch)" 
            dot={{ r: 4, fill: '#000', stroke: '#000', strokeWidth: 2 }}
            activeDot={{ r: 6, fill: '#fff', stroke: '#000', strokeWidth: 3 }}
          />
          <Line 
            key="line-data"
            type="monotone" 
            dataKey="ideal" 
            stroke="#94a3b8" 
            strokeWidth={2}
            strokeDasharray="10 10" 
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function VelocityChart() {
  return (
    <div className="h-[140px] w-full mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart id="velocity-chart-main" data={velocityData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <Bar key="bar-data" dataKey="points" radius={[4, 4, 0, 0]}>
            {velocityData.map((entry, index) => (
              <Cell 
                key={`cell-${entry.sprint}-${index}`} 
                fill="#fff" 
                stroke="#000"
                strokeWidth={2}
                fillOpacity={index === velocityData.length - 1 ? 1 : 0.4}
              />
            ))}
          </Bar>
          <Tooltip key="velocity-tooltip" cursor={{fill: 'transparent'}} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
