import type { Metadata } from "next";
import { ThemeProvider } from "@/lib/ThemeContext";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "OSINT Simulator",
  description: "Real-time OSINT maritime intelligence dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        style={{
          background: "var(--bg-primary)",
          color: "var(--text-primary)",
          margin: 0,
          height: "100vh",
          overflow: "hidden",
        }}
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
