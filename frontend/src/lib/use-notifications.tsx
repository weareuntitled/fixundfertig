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
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <NotificationContext.Provider value={{ notifications, notify, dismiss }}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        {notifications.map((n) => (
          <div
            key={n.id}
            className="pointer-events-auto rounded-xl px-4 py-3 shadow-lg text-sm font-medium max-w-sm cursor-pointer transition-all duration-300"
            style={{
              backgroundColor: n.type === "success" ? "#059669" : n.type === "error" ? "#dc2626" : "#1d1d1f",
              color: "#fff",
              animation: "slideIn 0.25s ease-out",
            }}
            onClick={() => dismiss(n.id)}
          >
            {n.message}
          </div>
        ))}
      </div>
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotification must be used within NotificationProvider");
  return ctx;
}
