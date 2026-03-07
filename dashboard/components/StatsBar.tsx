"use client";

import { Stats } from "@/types/invoice";
import { Loader2, CheckCircle, Clock, XCircle, AlertTriangle } from "lucide-react";

interface Props {
  stats?: Stats;
}

export function StatsBar({ stats }: Props) {
  const cards = [
    {
      label: "Processing",
      value: stats?.processing ?? 0,
      icon: <Loader2 size={20} className="animate-spin text-purple-400" />,
      cls: "border-purple-700/50 bg-purple-900/30",
      textCls: "text-purple-300",
    },
    {
      label: "Needs Review",
      value: stats?.pending_review ?? 0,
      icon: <AlertTriangle size={20} className="text-orange-400" />,
      cls: "border-orange-700/50 bg-orange-900/30",
      textCls: "text-orange-300",
    },
    {
      label: "Auto-Approved",
      value: stats?.paid ?? 0,
      icon: <CheckCircle size={20} className="text-green-400" />,
      cls: "border-green-700/50 bg-green-900/30",
      textCls: "text-green-300",
    },
    {
      label: "Rejected",
      value: stats?.rejected ?? 0,
      icon: <XCircle size={20} className="text-red-400" />,
      cls: "border-red-700/50 bg-red-900/30",
      textCls: "text-red-300",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
      {cards.map((c) => (
        <div key={c.label} className={`rounded-xl border p-5 flex items-center gap-3 ${c.cls}`}>
          {c.icon}
          <div>
            <p className="text-xs text-gray-500">{c.label}</p>
            <p className={`text-3xl font-bold ${c.textCls}`}>{c.value}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
