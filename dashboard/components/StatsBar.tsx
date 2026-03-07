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
      icon: <Loader2 size={20} className="animate-spin text-purple-600" />,
      cls: "border-purple-200 bg-purple-50",
      textCls: "text-purple-700",
    },
    {
      label: "Needs Review",
      value: stats?.pending_review ?? 0,
      icon: <AlertTriangle size={20} className="text-orange-500" />,
      cls: "border-orange-200 bg-orange-50",
      textCls: "text-orange-700",
    },
    {
      label: "Auto-Approved",
      value: stats?.paid ?? 0,
      icon: <CheckCircle size={20} className="text-green-600" />,
      cls: "border-green-200 bg-green-50",
      textCls: "text-green-700",
    },
    {
      label: "Rejected",
      value: stats?.rejected ?? 0,
      icon: <XCircle size={20} className="text-red-500" />,
      cls: "border-red-200 bg-red-50",
      textCls: "text-red-700",
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
