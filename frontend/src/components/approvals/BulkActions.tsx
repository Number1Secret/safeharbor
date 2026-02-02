"use client";

interface BulkActionsProps {
  selectedCount: number;
  totalCount: number;
  onSelectAll: () => void;
  onBulkApprove: () => void;
}

export function BulkActions({
  selectedCount,
  totalCount,
  onSelectAll,
  onBulkApprove,
}: BulkActionsProps) {
  const allSelected = selectedCount === totalCount;

  return (
    <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-200">
      <div className="flex items-center gap-3">
        <button
          onClick={onSelectAll}
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          {allSelected ? "Deselect All" : "Select All"}
        </button>
        <span className="text-sm text-gray-500">
          {selectedCount} of {totalCount} selected
        </span>
      </div>

      <div className="flex items-center gap-2">
        {selectedCount > 0 && (
          <>
            <button
              onClick={onBulkApprove}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              Approve Selected ({selectedCount})
            </button>
            <button className="px-4 py-2 text-sm bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
              Reject Selected
            </button>
          </>
        )}
      </div>
    </div>
  );
}
