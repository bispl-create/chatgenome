import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VCF Evidence Copilot",
  description: "Grounded VCF analysis with evidence, annotations, and async jobs.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
