import { Link } from "react-router-dom";

import type { NotificationRecord } from "../../types/alerts.ts";
import { formatIst } from "../../utils/quote.ts";

export function NotificationPopup({
  note,
  onDismiss,
}: {
  note: NotificationRecord;
  onDismiss: () => void;
}) {
  return (
    <div
      role="status"
      className="fixed right-4 bottom-4 z-30 w-full max-w-sm rounded-lg border border-slate-200 bg-white p-4 shadow-lg"
    >
      <p className="text-sm font-medium">{note.symbol}</p>
      <p className="mt-1 text-sm text-slate-700">{note.message}</p>
      <p className="mt-1 text-xs text-slate-500">{formatIst(note.triggered_at)}</p>
      <div className="mt-3 flex gap-3 text-sm">
        <Link className="text-slate-900" to={`/alerts/${note.alert_id}`}>
          Open alert
        </Link>
        <button type="button" className="text-slate-600" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </div>
  );
}
