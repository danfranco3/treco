import type { Metadata } from "next";
import "./globals.css";
import { WorkspaceProvider } from "@/lib/workspace";
import { StreamProvider } from "@/lib/StreamProvider";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { CommandPaletteProvider } from "@/components/ui/CommandPaletteProvider";

export const metadata: Metadata = {
  title: "Treco",
  description: "Real-time agent observability for your tickets",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="flex h-screen overflow-hidden bg-bg text-text-primary">
        <WorkspaceProvider>
          <StreamProvider>
            <CommandPaletteProvider />
            <Sidebar />
            <div className="flex flex-col flex-1 min-w-0">
              <TopBar />
              <main className="flex-1 overflow-y-auto p-6">{children}</main>
            </div>
          </StreamProvider>
        </WorkspaceProvider>
      </body>
    </html>
  );
}
