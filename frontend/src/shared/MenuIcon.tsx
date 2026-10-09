import type { Menu } from "./menuCatalog";

export function MenuIcon({
  menu,
  kind,
}: {
  menu?: Menu;
  kind?: "plus" | "close" | "star" | "up" | "down" | "grid";
}) {
  let drawing;
  if (kind === "plus") drawing = <path d="M12 5v14M5 12h14" />;
  else if (kind === "close") drawing = <path d="m6 6 12 12M18 6 6 18" />;
  else if (kind === "star")
    drawing = (
      <path d="m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.4-5.7-3-5.7 3 1.1-6.4L2.8 9.7l6.4-.9Z" />
    );
  else if (kind === "up") drawing = <path d="m6 14 6-6 6 6" />;
  else if (kind === "down") drawing = <path d="m6 10 6 6 6-6" />;
  else if (kind === "grid")
    drawing = (
      <>
        <rect x="4" y="4" width="6" height="6" rx="1" />
        <rect x="14" y="4" width="6" height="6" rx="1" />
        <rect x="4" y="14" width="6" height="6" rx="1" />
        <rect x="14" y="14" width="6" height="6" rx="1" />
      </>
    );
  else if (menu?.path === "board")
    drawing = (
      <>
        <path d="m4 10 14-5v14L4 14Z" />
        <path d="M8 14v6h3v-5M21 8v8" />
      </>
    );
  else if (menu?.module === "wms")
    drawing = (
      <>
        <path d="m12 3 9 5-9 5-9-5Zm-9 5v10l9 5 9-5V8M12 13v10M7.5 5.5l9 5" />
      </>
    );
  else if (menu?.path === "dashboard" || menu?.group.includes("분석"))
    drawing = (
      <>
        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      </>
    );
  else if (menu?.path === "pending")
    drawing = (
      <>
        <path d="M5 3h11l3 3v15H5ZM15 3v4h4M8 13l3 3 5-7" />
      </>
    );
  else if (menu?.path === "documents")
    drawing = (
      <>
        <rect x="5" y="5" width="14" height="16" rx="2" />
        <rect x="9" y="2" width="6" height="5" rx="1" />
        <path d="M9 12h6M9 16h6" />
      </>
    );
  else
    drawing = (
      <>
        <path d="M5 3h10l4 4v14H5ZM15 3v5h4M9 12h6M9 16h6" />
      </>
    );
  return (
    <svg
      viewBox="0 0 24 24"
      width="24"
      height="24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {drawing}
    </svg>
  );
}
