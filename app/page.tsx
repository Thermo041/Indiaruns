import { TalentDashboard } from "@/components/dashboard/talent-dashboard";

export default function Home() {
  // VERCEL is set on Vercel builds; used to render the dashboard in read-only
  // demo mode (local-only actions like live ranking/validation are disabled).
  const hosted = Boolean(process.env.VERCEL);
  return <TalentDashboard hosted={hosted} />;
}
