import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Redrob Talent Ranker",
  description: "Local, free, CPU-only candidate ranking dashboard for the India Runs Data & AI Challenge.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

