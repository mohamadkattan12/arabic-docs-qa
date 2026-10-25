import type { Metadata } from "next";
import { Geist, Noto_Sans_Arabic } from "next/font/google";
import { Nav } from "@/components/nav";
import { Providers } from "@/components/providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const notoArabic = Noto_Sans_Arabic({ variable: "--font-arabic", subsets: ["arabic"] });

export const metadata: Metadata = {
  title: "Arabic Docs Q&A",
  description: "Ask company documents questions in Arabic or English and get cited answers.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${notoArabic.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <Providers>
          <Nav />
          <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
