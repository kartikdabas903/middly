import type { Metadata } from "next"
import { Geist_Mono, Inter } from "next/font/google"

import "./globals.css"
import { Providers } from "./providers"

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] })
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] })

export const metadata: Metadata = {
  title: { default: "Middly — Connected public services", template: "%s · Middly" },
  description:
    "Middly connects department systems so citizens apply once, consent to how their data is shared, and track every application in one place.",
  robots: { index: false, follow: false },
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
