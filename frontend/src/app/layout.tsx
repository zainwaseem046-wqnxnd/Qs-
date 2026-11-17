import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/components/providers";
import { themeInitScript } from "@/components/shell/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "QS Intelligence USA", template: "%s · QS Intelligence USA" },
  description: "The AI Commercial Operating System for Construction.",
  manifest: "/manifest.webmanifest",
  applicationName: "QS Intelligence USA",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f8fb" },
    { media: "(prefers-color-scheme: dark)", color: "#07111f" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-US" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
