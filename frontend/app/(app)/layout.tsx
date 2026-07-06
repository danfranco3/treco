import { WorkspaceProvider } from "@/lib/workspace";
import { StreamProvider } from "@/lib/StreamProvider";
import { AppShell } from "@/components/layout/AppShell";
import { CommandPaletteProvider } from "@/components/ui/CommandPaletteProvider";
import { KeyboardShortcutsProvider } from "@/components/ui/KeyboardShortcutsProvider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-white focus:text-[#166534] focus:rounded-lg focus:shadow-lg focus:border focus:border-[#16a34a] focus:font-medium focus:text-sm"
      >
        Skip to main content
      </a>
      <WorkspaceProvider>
        <StreamProvider>
          <CommandPaletteProvider />
          <KeyboardShortcutsProvider />
          <AppShell>{children}</AppShell>
        </StreamProvider>
      </WorkspaceProvider>
    </>
  );
}
