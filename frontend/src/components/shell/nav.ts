import {
  BarChart3,
  Bot,
  Briefcase,
  Building2,
  Calculator,
  ClipboardCheck,
  Database,
  FileSignature,
  FileText,
  FolderKanban,
  Gavel,
  GitPullRequestArrow,
  HardHat,
  LayoutDashboard,
  LineChart,
  ListTree,
  Ruler,
  Settings,
  ShieldCheck,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  icon: LucideIcon;
  href?: string;
  /** Roadmap phase for modules not yet delivered. Rendered as non-interactive labels. */
  phase?: number;
}

export const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Portfolio",
    items: [
      { label: "Executive Dashboard", icon: LayoutDashboard, href: "/dashboard" },
      { label: "Projects", icon: FolderKanban, href: "/projects" },
      { label: "Directory", icon: Building2, href: "/directory" },
    ],
  },
  {
    section: "Preconstruction",
    items: [
      { label: "Estimating", icon: Calculator, href: "/estimating" },
      { label: "Cost Codes", icon: ListTree, href: "/cost-codes" },
      { label: "AI Measurement", icon: Ruler, phase: 5 },
      { label: "Cost Database", icon: Database, phase: 2 },
      { label: "Procurement", icon: Gavel, phase: 3 },
    ],
  },
  {
    section: "Commercial",
    items: [
      { label: "Contracts", icon: FileSignature, phase: 2 },
      { label: "Subcontracts", icon: Briefcase, phase: 3 },
      { label: "Change Orders", icon: GitPullRequestArrow, phase: 2 },
      { label: "Pay Applications", icon: Wallet, phase: 3 },
      { label: "Cost Management", icon: BarChart3, phase: 2 },
      { label: "Forecasting", icon: LineChart, phase: 2 },
    ],
  },
  {
    section: "Operations",
    items: [
      { label: "Field Operations", icon: HardHat, phase: 5 },
      { label: "Documents", icon: FileText, href: "/documents" },
      { label: "Compliance", icon: ClipboardCheck, phase: 5 },
    ],
  },
  {
    section: "Intelligence",
    items: [
      { label: "AI Commercial Director", icon: Bot, phase: 4 },
      { label: "Analytics", icon: ShieldCheck, phase: 2 },
    ],
  },
  { section: "Settings", items: [{ label: "Administration", icon: Settings, href: "/admin" }] },
];
