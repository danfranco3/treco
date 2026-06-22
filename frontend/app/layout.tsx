import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Treco — Real-time observability for AI agents",
  description: "See what your AI coding agents are doing in real time. Live kanban, acceptance criteria tracking, token cost per session. Open source.",
  openGraph: {
    title: "Treco — Real-time observability for AI agents",
    description: "See what your AI coding agents are doing in real time. Live kanban, acceptance criteria tracking, token cost per session. Open source.",
    url: "https://treco.dev",
    siteName: "Treco",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Treco — Real-time observability for AI agents",
    description: "See what your AI coding agents are doing in real time.",
  },
};

// Inline script runs synchronously before React hydrates — prevents flash of wrong theme.
const themeScript = `
(function(){
  try {
    var t = localStorage.getItem('theme') || 'system';
    var dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  } catch(e){}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="bg-[var(--bg)] text-[var(--text)]">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
