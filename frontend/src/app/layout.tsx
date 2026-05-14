import "./globals.css";
import { ReactNode } from "react";
import type { Metadata } from "next";
import {NextIntlClientProvider} from "next-intl";
import {getLocale, getMessages} from "next-intl/server";

export const metadata: Metadata = {
  title: {
    default: "Atlas — school workspace",
    template: "%s — Atlas"
  },
  description: "School timetable, curriculum, and scheduling workspace."
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
