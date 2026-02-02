"use client";

import { clsx } from "clsx";
import { ConfidenceIndicator } from "./ConfidenceIndicator";

interface ClassificationCardProps {
  employee: {
    id: string;
    first_name: string;
    last_name: string;
    job_title: string | null;
    department: string | null;
    ttoc_code: string | null;
    ttoc_title: string | null;
    classification_confidence: number | null;
    classification_reasoning: string | null;
    is_tipped_occupation: boolean | null;
  };
  isSelected: boolean;
  onToggleSelect: () => void;
}

export function ClassificationCard({
  employee,
  isSelected,
  onToggleSelect,
}: ClassificationCardProps) {
  const confidence = employee.classification_confidence || 0;

  return (
    <div
      className={clsx(
        "bg-white rounded-xl border p-5 transition-all",
        isSelected
          ? "border-blue-400 ring-2 ring-blue-100"
          : "border-gray-200 hover:border-gray-300"
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <div>
            <p className="text-sm font-semibold text-gray-900">
              {employee.first_name} {employee.last_name}
            </p>
            <p className="text-xs text-gray-500">
              {employee.job_title || "No title"} &middot;{" "}
              {employee.department || "No department"}
            </p>
          </div>
        </div>
        <ConfidenceIndicator score={confidence} />
      </div>

      {/* Classification */}
      {employee.ttoc_code ? (
        <div className="mt-4 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-600">
                TTOC Classification
              </p>
              <p className="text-sm font-semibold text-gray-900 mt-0.5">
                {employee.ttoc_code} - {employee.ttoc_title}
              </p>
            </div>
            {employee.is_tipped_occupation !== null && (
              <span
                className={clsx(
                  "text-xs px-2 py-1 rounded-full font-medium",
                  employee.is_tipped_occupation
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-600"
                )}
              >
                {employee.is_tipped_occupation ? "Tipped" : "Non-Tipped"}
              </span>
            )}
          </div>

          {employee.classification_reasoning && (
            <p className="text-xs text-gray-500 mt-2">
              {employee.classification_reasoning}
            </p>
          )}
        </div>
      ) : (
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-xs text-yellow-700 font-medium">
            Needs Classification
          </p>
          <p className="text-xs text-yellow-600 mt-0.5">
            Run AI classification to assign a TTOC code
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4">
        {employee.ttoc_code && (
          <>
            <button className="flex-1 px-3 py-2 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
              Confirm
            </button>
            <button className="flex-1 px-3 py-2 text-xs bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
              Change Code
            </button>
            <button className="px-3 py-2 text-xs bg-white border border-gray-300 text-gray-400 rounded-lg hover:bg-gray-50 transition-colors">
              Skip
            </button>
          </>
        )}
        {!employee.ttoc_code && (
          <button className="flex-1 px-3 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            Run Classification
          </button>
        )}
      </div>
    </div>
  );
}
