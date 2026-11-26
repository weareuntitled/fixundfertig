import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

export interface Notification {
  id: string;
  type: "success" | "error" | "info";
  message: string;
}

interface NotificationContextType {
  notifications: Notification[];
  notify: (type: Notification["type"], message: string) => void;
  dismiss: (id: string) => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

let _id = 0;
function nextId() {
  return `n_${++_id}_${Date.now()}`;
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const notify = useCallback((type: Notification["type"], message: string) => {
    const id = nextId();
    setNotifications((prev) => [...prev, { id, type, message }]);
    // Errors stay until closed: they often need reading twice or acting on.
    if (type !== "error") {
      setTimeout(() => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
      }, 6000);
    }
  }, []);

  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const errors = notifications.filter((n) => n.type === "error");
  const others = notifications.filter((n) => n.type !== "error");

  // Both live regions exist before any message, so screen readers announce what is added.
  return (
    <NotificationContext.Provider value={{ notifications, notify, dismiss }}>
      {children}
      <div className="fixed top-4 right-4 left-4 z-[100] flex flex-col items-end gap-2 pointer-events-none sm:left-auto">
        <div role="alert" className="flex flex-col items-end gap-2">
          {errors.map((n) => (
            <div
              key={n.id}
              className="pointer-events-auto flex max-w-sm items-start gap-2 rounded-xl py-2 pl-4 pr-1 text-sm font-medium text-white shadow-lg"
              style={{ backgroundColor: TOAST_COLORS.error, animation: "slideIn 0.25s ease-out" }}
            >
              <span className="py-1.5">{n.message}</span>
              <button
                type="button"
                aria-label="Meldung schließen"
                onClick={() => dismiss(n.id)}
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-lg leading-none hover:bg-white/15"
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>
          ))}
        </div>
        <div role="status" aria-live="polite" className="flex flex-col items-end gap-2">
          {others.map((n) => (
            <div
              key={n.id}
              className="pointer-events-auto max-w-sm cursor-pointer rounded-xl px-4 py-3 text-sm font-medium text-white shadow-lg"
              style={{ backgroundColor: TOAST_COLORS[n.type], animation: "slideIn 0.25s ease-out" }}
              onClick={() => dismiss(n.id)}
            >
              {n.message}
            </div>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          @keyframes slideIn { from { opacity: 1; } to { opacity: 1; } }
        }
      `}</style>
    </NotificationContext.Provider>
  );
}

/** White text on each reaches at least 4.5:1. */
const TOAST_COLORS: Record<Notification["type"], string> = {
  success: "#047857",
  error: "#c81e1e",
  info: "#1d1d1f",
};

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotification must be used within NotificationProvider");
  return ctx;
}
