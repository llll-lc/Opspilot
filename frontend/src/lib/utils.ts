// 源自 langchain-ai/agent-chat-ui@325517352ca3672c8bc0745c4143b2301dd74997（MIT）。
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
