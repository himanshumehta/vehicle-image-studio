import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vehicle Image Studio",
  description: "Background removal, upscaling and plate/watermark clean-up for vehicle photos",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-surface text-th-primary min-h-screen">{children}</body>
    </html>
  );
}
