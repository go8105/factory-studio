import { Children } from "react";
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
// 문서 목차(P-05)가 가리킬 수 있게 ## 제목에 id를 붙인다.
export const slug = (text: string) =>
  text.replace(/[*`]/g, "").trim().replace(/\s+/g, "-");
export function MarkdownContent({ body }: { body: string }) {
  return (
    <article className="markdown">
      <Markdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          h2: ({ children }) => (
            <h2 id={slug(Children.toArray(children).join(""))}>{children}</h2>
          ),
        }}
      >
        {body}
      </Markdown>
    </article>
  );
}
