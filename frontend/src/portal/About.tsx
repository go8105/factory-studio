import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../shared/components";
import profile from "../../../content/about/profile.json";
import "./About.css";

const sections = [
  ["intro", "소개"],
  ["career", "경력"],
  ["projects", "프로젝트"],
  ["skills", "기술 스택"],
  ["awards", "수상·자격·교육"],
  ["notes", "기술 노트"],
  ["contact", "연락"],
];
const groups = ["FEMS", "MES", "개인"];
type Project = (typeof profile.projects)[number];
function Chips({ items }: { items: string[] }) {
  return (
    <div className="about-chips">
      {items.map((item) => (
        <Badge key={item}>{item}</Badge>
      ))}
    </div>
  );
}
function Heading({ label, title }: { label: string; title: string }) {
  return (
    <header className="about-heading">
      <p className="about-eyebrow">{label}</p>
      <h2>{title}</h2>
    </header>
  );
}
function ProjectCard({ project }: { project: Project }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article
      className="about-card about-project"
      id={project.id}
      aria-labelledby={`${project.id}-title`}
    >
      <div>
        <p className="about-meta">{project.period || project.group}</p>
        <h3 id={`${project.id}-title`}>{project.title}</h3>
      </div>
      <div className="about-result">
        <small>성과</small>
        <strong>{project.result}</strong>
      </div>
      {expanded && (
        <div className="about-details" id={`${project.id}-details`}>
          {project.problem && (
            <dl>
              <dt>문제</dt>
              <dd>{project.problem}</dd>
            </dl>
          )}
          <dl>
            <dt>{project.problem ? "해결" : "소개"}</dt>
            <dd>{project.solution}</dd>
          </dl>
          {project.link && <Link to={project.link}>프로젝트 보기 →</Link>}
        </div>
      )}
      <button
        type="button"
        className="link-button"
        aria-label={`${expanded ? "접기" : "자세히 보기"} · ${project.title}`}
        aria-expanded={expanded}
        aria-controls={`${project.id}-details`}
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? "접기" : "자세히 보기"}
      </button>
    </article>
  );
}
export type AboutNote = {
  slug: string;
  title: string;
  date: string;
  category: string;
  summary: string;
};
const noNotes: AboutNote[] = [];
export function About({ notes = noNotes }: { notes?: AboutNote[] }) {
  const latestNotes = [...notes]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 3);
  const [group, setGroup] = useState("FEMS");
  const [active, setActive] = useState("intro");
  useEffect(() => {
    const previous = document.title;
    document.title = `${profile.name} · 제조 IT 개발자`;
    const update = () => {
      let current = "intro";
      for (const [id] of sections) {
        if (
          (document.getElementById(id)?.getBoundingClientRect().top ??
            Infinity) <= 140
        )
          current = id;
      }
      if (
        window.scrollY > 0 &&
        window.innerHeight + window.scrollY >=
          document.documentElement.scrollHeight - 2
      )
        current = "contact";
      setActive(current);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      document.title = previous;
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [notes.length]);
  return (
    <div className="about-page">
      <header className="about-top">
        <div className="about-top-inner">
          <a
            className="about-brand"
            href="#intro"
            aria-label={`${profile.name} 소개`}
          >
            HKH
          </a>
          <nav aria-label="주요 메뉴">
            <a href="#intro">소개</a>
            <a href="#projects">프로젝트</a>
            <Link className="button secondary" to="/">
              EIP 체험하기 →
            </Link>
          </nav>
        </div>
      </header>
      <div className="about-layout">
        <nav className="about-nav" aria-label="섹션 목차">
          <p>목차</p>
          {sections
            .filter(([id]) => id !== "notes" || notes.length > 0)
            .map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                aria-current={active === id ? "location" : undefined}
              >
                {label}
              </a>
            ))}
        </nav>
        <main className="about-main" id="main">
          <section
            className="about-section about-hero"
            id="intro"
            aria-labelledby="about-name"
          >
            <div className="about-intro">
              <p className="about-eyebrow">{profile.role}</p>
              <h1 id="about-name">{profile.name}</h1>
              <p className="about-tagline">{profile.tagline}</p>
              <p>{profile.bio}</p>
              <div className="about-actions">
                <a className="button" href={`mailto:${profile.contact.email}`}>
                  이메일 보내기
                </a>
                <a className="button secondary" href={profile.contact.github}>
                  GitHub
                </a>
              </div>
            </div>
            <div>
              {profile.stats.map(([value, label]) => (
                <div className="about-stat" key={value}>
                  <strong>{value}</strong>
                  <p>{label}</p>
                </div>
              ))}
            </div>
          </section>
          <section className="about-section" id="career" aria-label="경력">
            <Heading label="CAREER" title="경력" />
            <div className="about-grid">
              {profile.careers.map((career) => (
                <article className="about-card" key={career.company}>
                  <p className="about-meta">{career.period}</p>
                  <h3>{career.company}</h3>
                  <p>{career.role}</p>
                  <Chips items={career.stack} />
                  <a
                    href="#projects"
                    className="link-button"
                    onClick={() => setGroup(career.group)}
                  >
                    {career.group} 프로젝트 보기 →
                  </a>
                </article>
              ))}
            </div>
          </section>
          <section
            className="about-section"
            id="projects"
            aria-label="프로젝트"
          >
            <Heading label="PROJECTS" title="문제 → 해결 → 성과" />
            <div className="tabs" role="group" aria-label="프로젝트 분류">
              {groups.map((item) => (
                <button
                  type="button"
                  key={item}
                  aria-pressed={group === item}
                  onClick={() => setGroup(item)}
                >
                  {item}{" "}
                  {profile.projects.filter((p) => p.group === item).length}
                </button>
              ))}
            </div>
            <div className="about-grid">
              {profile.projects
                .filter((p) => p.group === group)
                .map((project) => (
                  <ProjectCard key={project.id} project={project} />
                ))}
            </div>
          </section>
          <section className="about-section" id="skills" aria-label="기술 스택">
            <Heading label="SKILLS" title="기술 스택" />
            {profile.stacks.map((stack) => (
              <div className="about-stack" key={stack.label}>
                <h3>{stack.label}</h3>
                <Chips items={stack.items} />
              </div>
            ))}
          </section>
          <section
            className="about-section"
            id="awards"
            aria-label="수상 · 자격 · 교육"
          >
            <Heading
              label="AWARDS · CERTS · EDUCATION"
              title="수상 · 자격 · 교육"
            />
            <div className="about-grid about-awards">
              {[
                { label: "수상 · 자격", items: profile.awards },
                { label: "교육 · 학력 · 외국어", items: profile.education },
              ].map(({ label, items }) => (
                <div key={label}>
                  <h3>{label}</h3>
                  <ul>
                    {items.map(([date, text]) => (
                      <li key={text}>
                        <time>{date}</time>
                        <span>{text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
          {latestNotes.length > 0 && (
            <section
              className="about-section"
              id="notes"
              aria-label="기술 노트"
            >
              <div className="about-notes-heading">
                <Heading label="TECH NOTES" title="기술 노트" />
                <Link to="/notes">전체 보기 →</Link>
              </div>
              <div className="about-notes-grid">
                {latestNotes.map((note) => (
                  <Link
                    className="about-card"
                    key={note.slug}
                    to={`/notes/${note.slug}`}
                  >
                    <p className="about-eyebrow">{note.category}</p>
                    <h3>{note.title}</h3>
                    <p>{note.summary}</p>
                    <time className="about-meta">{note.date}</time>
                  </Link>
                ))}
              </div>
            </section>
          )}
          <section
            className="about-section about-contact"
            id="contact"
            aria-label="연락"
          >
            <div>
              <h2>같이 이야기해요</h2>
              <p>
                <a href={`mailto:${profile.contact.email}`}>
                  {profile.contact.email}
                </a>{" "}
                ·{" "}
                <a href={profile.contact.github}>
                  {profile.contact.github.replace("https://", "")}
                </a>
              </p>
            </div>
            <a
              className="button secondary"
              href={`mailto:${profile.contact.email}`}
            >
              이메일 보내기
            </a>
          </section>
        </main>
      </div>
    </div>
  );
}
