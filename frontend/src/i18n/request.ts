import {hasLocale} from "next-intl";
import {getRequestConfig} from "next-intl/server";
import {cookies, headers} from "next/headers";
import {readFile} from "node:fs/promises";
import path from "node:path";
import {routing} from "./routing";

function detectFromAcceptLanguage(value: string | null): string | undefined {
  if (!value) return undefined;
  const candidates = value
    .split(",")
    .map((part) => part.split(";")[0]?.trim().toLowerCase())
    .filter(Boolean);
  for (const candidate of candidates) {
    const primary = candidate.split("-")[0];
    if (hasLocale(routing.locales, primary)) return primary;
  }
  return undefined;
}

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const headerStore = await headers();
  const localeFromCookie = cookieStore.get("NEXT_LOCALE")?.value;
  const localeFromHeader = detectFromAcceptLanguage(headerStore.get("accept-language"));

  const locale = hasLocale(routing.locales, localeFromCookie)
    ? localeFromCookie
    : localeFromHeader ?? routing.defaultLocale;
  const messagePath = path.join(process.cwd(), "messages", `${locale}.json`);
  const messageFile = await readFile(messagePath, "utf-8");

  return {
    locale,
    messages: JSON.parse(messageFile)
  };
});
