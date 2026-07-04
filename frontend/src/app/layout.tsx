import type { Metadata } from "next";
import { Silkscreen, VT323 } from "next/font/google";
import "./globals.css";

const silkscreen = Silkscreen({
  variable: "--font-pixel",
  weight: ["400", "700"],
  subsets: ["latin"],
});

const vt323 = VT323({
  variable: "--font-mono-pixel",
  weight: "400",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sight-Text",
  description:
    "Sight-text takes in documents and Anki decks and converts them to make them more dyslexia friendly.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${silkscreen.variable} ${vt323.variable}`}>
      <body>{children}</body>
    </html>
  );
}
