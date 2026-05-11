import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import "./globals.css";
import { Providers } from "./providers";
import { AppLayout } from "@/components/layout/AppLayout";

export const metadata: Metadata = {
  title: "Malaysia Intelligence Monitor | AI Social Surveillance",
  description: "Real-time AI-powered social media monitoring and narrative intelligence platform for Malaysia",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-intelligence min-h-screen font-sans antialiased">
        <Providers>
          <AppLayout>{children}</AppLayout>
        </Providers>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "#0c1428",
              color: "#e2e8f0",
              border: "1px solid #1a2744",
              fontSize: "13px",
              fontFamily: "JetBrains Mono, monospace",
            },
            error: { iconTheme: { primary: "#ff3366", secondary: "#0c1428" } },
            success: { iconTheme: { primary: "#00ff88", secondary: "#0c1428" } },
          }}
        />
      </body>
    </html>
  );
}
