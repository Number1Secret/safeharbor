import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/shared/AppShell";

export const metadata: Metadata = {
  title: "SafeHarbor AI - OBBB Tax Compliance",
  description: "Automated OBBB tax exemption calculation engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
