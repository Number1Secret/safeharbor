"use client";

interface CalculationBreakdownProps {
  employeeId: string;
}

export function CalculationBreakdown({ employeeId }: CalculationBreakdownProps) {
  // Latest calculation breakdown - in production, fetch from API
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Latest Calculation Breakdown
      </h3>

      <div className="space-y-4">
        {/* Regular Rate Section */}
        <section>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Regular Rate of Pay (FLSA Section 7)
          </h4>
          <div className="bg-gray-50 rounded-lg p-4">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-gray-200">
                <Row label="Base Hourly Wages" formula="Rate x Hours" value="--" />
                <Row label="Shift Differentials" value="--" />
                <Row label="Non-Discretionary Bonuses" value="--" />
                <Row label="Commissions" value="--" />
                <Row
                  label="Total Compensation"
                  value="--"
                  className="font-semibold"
                />
                <Row label="Total Hours Worked" value="--" />
                <Row
                  label="Regular Rate"
                  formula="Total Comp / Total Hours"
                  value="--"
                  className="font-bold text-blue-700"
                />
              </tbody>
            </table>
          </div>
        </section>

        {/* OT Premium Section */}
        <section>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Qualified Overtime Premium
          </h4>
          <div className="bg-blue-50 rounded-lg p-4">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-blue-100">
                <Row label="Regular Rate" value="--" />
                <Row label="OT Multiplier" value="0.5x" />
                <Row label="Qualified OT Hours" value="--" />
                <Row
                  label="Qualified OT Premium"
                  formula="Rate x 0.5 x Hours"
                  value="--"
                  className="font-bold text-blue-700"
                />
              </tbody>
            </table>
          </div>
        </section>

        {/* Tip Credit Section */}
        <section>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Tip Credit (TTOC Qualified)
          </h4>
          <div className="bg-green-50 rounded-lg p-4">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-green-100">
                <Row label="TTOC Code" value="--" />
                <Row label="Cash Tips" value="--" />
                <Row label="Charged Tips" value="--" />
                <Row label="Tip Pool Adjustment" value="--" />
                <Row
                  label="Qualified Tip Credit"
                  value="--"
                  className="font-bold text-green-700"
                />
              </tbody>
            </table>
          </div>
        </section>

        {/* Phase-Out */}
        <section>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            MAGI Phase-Out
          </h4>
          <div className="bg-orange-50 rounded-lg p-4">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-orange-100">
                <Row label="Estimated Annual MAGI" value="--" />
                <Row label="Filing Status" value="--" />
                <Row label="Phase-Out Percentage" value="--" />
                <Row
                  label="Final Credit Amount"
                  value="--"
                  className="font-bold text-orange-700"
                />
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function Row({
  label,
  formula,
  value,
  className,
}: {
  label: string;
  formula?: string;
  value: string;
  className?: string;
}) {
  return (
    <tr className={className}>
      <td className="py-2 text-gray-600">
        {label}
        {formula && (
          <span className="text-xs text-gray-400 ml-1">({formula})</span>
        )}
      </td>
      <td className="py-2 text-right tabular-nums">{value}</td>
    </tr>
  );
}
