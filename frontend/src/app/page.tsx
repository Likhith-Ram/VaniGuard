import type { Metadata } from "next";
import DashboardClient from "@/components/DashboardClient";

export const metadata: Metadata = {
  title: "Live Dashboard",
  description:
    "Live AI voice detection dashboard — monitor calls in real time, review audit logs, and inspect model telemetry.",
};

// Server component: exports metadata, renders the interactive client component
export default function Home() {
  return <DashboardClient />;
}
