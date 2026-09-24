import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
const helpFiles = import.meta.glob("../../../content/help/**/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;
const cardFiles = import.meta.glob("../../../content/cards/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;
export const help = Object.fromEntries(
  Object.entries(helpFiles).map(([path, body]) => [
    path.split("/help/")[1].replace(".md", ""),
    body,
  ]),
);
export const cards = Object.fromEntries(
  Object.entries(cardFiles).map(([path, body]) => [
    path.split("/").pop()!.replace(".md", ""),
    body,
  ]),
);
export const contentTitle = (body: string) =>
  body.split("\n")[0].replace(/^#\s*/, "");
export function MarkdownContent({ body }: { body: string }) {
  return (
    <article className="markdown">
      <Markdown remarkPlugins={[remarkGfm]} skipHtml>
        {body}
      </Markdown>
    </article>
  );
}
