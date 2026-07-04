import type { Metadata } from "next";
import { Silkscreen, VT323 } from "next/font/google";
import localFont from "next/font/local";
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

const openDyslexic = localFont({
  variable: "--font-dyslexic",
  src: [
    {
      path: "./fonts/OpenDyslexic-Regular.woff",
      weight: "400",
      style: "normal",
    },
    {
      path: "./fonts/OpenDyslexic-Bold.woff",
      weight: "700",
      style: "normal",
    },
    {
      path: "./fonts/OpenDyslexic-Italic.woff",
      weight: "400",
      style: "italic",
    },
  ],
});

export const metadata: Metadata = {
  title: "Clarity",
  description:
    "Clarity takes in documents and Anki decks and converts them to make them more dyslexia friendly.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${silkscreen.variable} ${vt323.variable} ${openDyslexic.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
