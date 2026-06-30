/**
 * @schema NavItems
 * @purpose Navigation item definitions for sidebar and bottom nav
 * @input None (static configuration)
 * @output Array of NavItem objects with id, label, icon, and route path
 * @tokens None (consumed by sidebar/bottom-nav components)
 */
import {
  LayoutDashboard,
  FileText,
  Users,
  Folder,
  BookOpen,
  Download,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  to: string;
}

export const navItems: readonly NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, to: "/" },
  { id: "invoices", label: "Rechnungen", icon: FileText, to: "/invoices" },
  { id: "customers", label: "Kunden", icon: Users, to: "/customers" },
  { id: "documents", label: "Belege", icon: Folder, to: "/documents" },
  { id: "ledger", label: "Buchhaltung", icon: BookOpen, to: "/ledger" },
  { id: "exports", label: "Exports", icon: Download, to: "/exports" },
  { id: "settings", label: "Einstellungen", icon: Settings, to: "/settings" },
] as const;
