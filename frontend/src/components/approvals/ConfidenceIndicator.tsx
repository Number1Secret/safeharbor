"use client";

import { clsx } from "clsx";

interface ConfidenceIndicatorProps {
  score: number; // 0-1
  showLabel?: boolean;
}

export function ConfidenceIndicator({
  score,
  showLabel = true,
}: ConfidenceIndicatorProps) {
  const percentage = Math.round(score * 100);

  const getColor = () => {
    if (percentage >= 90) return { bg: "bg-green-500", text: "text-green-700", label: "High" };
    if (percentage >= 70) return { bg: "bg-yellow-500", text: "text-yellow-700", label: "Medium" };
    if (percentage >= 50) return { bg: "bg-orange-500", text: "text-orange-700", label: "Low" };
    return { bg: "bg-red-500", text: "text-red-700", label: "Very Low" };
  };

  const config = getColor();

  return (
    <div className="flex items-center gap-2">
      {/* Progress Ring */}
      <div className="relative w-10 h-10">
        <svg className="w-10 h-10 -rotate-90" viewBox="0 0 36 36">
          <circle
            cx="18"
            cy="18"
            r="14"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="3"
          />
          <circle
            cx="18"
            cy="18"
            r="14"
            fill="none"
            className={config.bg.replace("bg-", "stroke-")}
            strokeWidth="3"
            strokeDasharray={`${percentage * 0.88} 88`}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-gray-700">
          {percentage}
        </span>
      </div>
      {showLabel && (
        <span className={clsx("text-xs font-medium", config.text)}>
          {config.label}
        </span>
      )}
    </div>
  );
}
