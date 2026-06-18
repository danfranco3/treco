import { WorkspaceProvider } from "@/lib/workspace";
import { StreamProvider } from "@/lib/StreamProvider";
import { AppShell } from "@/components/layout/AppShell";
import { CommandPaletteProvider } from "@/components/ui/CommandPaletteProvider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <WorkspaceProvider>
      <StreamProvider>
        <CommandPaletteProvider />
        <AppShell>{children}</AppShell>
      </StreamProvider>
    </WorkspaceProvider>
  );
}
