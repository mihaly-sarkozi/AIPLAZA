import DOMPurify from "dompurify";

/**
 * Sanitize text for safe display in the chat UI.
 * Strips all HTML tags and prevents script execution.
 * Use for both user and assistant messages before rendering.
 */
export function sanitizeMessage(text: string): string {
  if (typeof text !== "string") return "";
  if (typeof document === "undefined") {
    return text.replace(/<[^>]*>/g, "");
  }
  return DOMPurify.sanitize(text, { ALLOWED_TAGS: [] });
}
