import type { ReactNode } from 'react';

function Monogram({ size = 40, color = 'currentColor' }: { size?: number; color?: string }) {
  return (
    <svg
      aria-label="HYUDO HD monogram"
      height={size}
      viewBox="0 0 46 40"
      width={size * 1.15}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M4 4V36M4 20H24M24 4V36M24 4H29C37.3 4 42 10.7 42 20C42 29.3 37.3 36 29 36H24" stroke={color} strokeWidth="1.5" />
      <path d="M29 20H36M33 17L36 20L33 23" stroke={color} strokeWidth="1.5" strokeLinecap="square" strokeLinejoin="miter" />
    </svg>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return <h2 className="section-label">{children}</h2>;
}

function MailIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="3.5" y="5.5" width="17" height="13" rx="0.5" />
      <path d="m4 6 8 7 8-7" />
    </svg>
  );
}

function GithubIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 3.5a8.5 8.5 0 0 0-2.7 16.56c.43.08.58-.18.58-.41v-1.68c-2.4.52-2.9-1.02-2.9-1.02-.39-1-1-1.27-1-1.27-.8-.55.06-.54.06-.54.88.07 1.35.91 1.35.91.79 1.35 2.07.96 2.57.73.08-.57.31-.96.56-1.18-1.92-.22-3.93-.96-3.93-4.2 0-.94.33-1.7.89-2.3-.09-.22-.39-1.1.08-2.27 0 0 .73-.23 2.34.88a8.2 8.2 0 0 1 4.25 0c1.62-1.1 2.34-.88 2.34-.88.47 1.17.17 2.05.08 2.27.56.6.9 1.36.9 2.3 0 3.25-2.02 3.98-3.94 4.2.31.27.59.8.59 1.62v2.43c0 .23.15.5.59.41A8.5 8.5 0 0 0 12 3.5Z" />
    </svg>
  );
}

const certificates = [
  ['정보처리기사 필기', '2025.05'],
  ['SQLD', '2025.06'],
  ['리눅스마스터 2급', '2026.04'],
  ['전산회계 2급', '2026.06'],
];

const careers = [
  {
    period: '2025.10 – 현재',
    company: '㈜와이씨코퍼레이션',
    role: 'FEMS 풀스택·PM',
    result: '이상 감지 지연 15분 → 5초',
  },
  {
    period: '2022.02 – 2025.03',
    company: '㈜엘앤코리아',
    role: '제조 MES 개발',
    result: '제조 현장 MES 5곳 구축·운영',
  },
];

export default function App() {
  const saveContact = () => {
    const vcard = [
      'BEGIN:VCARD',
      'VERSION:3.0',
      'N:황;경호;;;',
      'FN:황경호',
      'ORG:휴도 HYUDO',
      'TITLE:제조 IT 개발자 · 휴대용 비누 그라인더 메이커',
      'EMAIL;TYPE=INTERNET:go8105@gmail.com',
      'URL:https://www.hyudo.kr',
      'END:VCARD',
    ].join('\r\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([vcard], { type: 'text/vcard;charset=utf-8' }));
    link.download = 'hwang-kyoungho.vcf';
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <main className="site-shell">
      <section className="hero">
        <div className="hero-frame" aria-hidden="true" />
        <div className="hero-top">
          <Monogram />
          <p>CARRY IT ACROSS</p>
        </div>
        <div className="hero-content">
          <h1>휴도</h1>
          <p className="wordmark">H Y U D O</p>
          <p className="hero-role">황경호 · 제조 IT 개발자 · 휴대용 비누 그라인더 메이커</p>
          <p className="hero-summary">현장 데이터를 서비스까지 연결합니다. MES 4년, FEMS 1인 설계·운영.</p>
          <div className="hero-actions">
            <button type="button" onClick={saveContact}>연락처 저장</button>
            <a href="mailto:go8105@gmail.com">이메일</a>
          </div>
        </div>
      </section>

      <div className="content">
        <section className="meaning-block" aria-labelledby="meaning-title">
          <h2 id="meaning-title">携 渡</h2>
          <p className="hanja-reading">이끌 휴 · 건널 도</p>
          <div className="meaning-rule" />
          <p className="meaning-slogan">생각에서 손끝까지.</p>
        </section>

        <section>
          <SectionLabel>NOW MAKING</SectionLabel>
          <article className="product-card">
            <div className="product-image">
              {/* shortcut: v3 설계 렌더, 실물 사진이 오면 같은 경로로 교체 */}
              <img src="/images/soap-grinder.jpg" alt="휴대용 비누 그라인더" />
            </div>
            <div className="product-copy">
              <h3>휴대용 비누 그라인더</h3>
              <p>누르고 비틀어 비누를 가루로 — 여행·캠핑용 휴대 설계</p>
              <div className="badges">
                <span>시제품 개발 중</span>
                <span>모두의 창업 1라운드 합격</span>
              </div>
            </div>
          </article>
        </section>

        <section className="metrics" aria-label="주요 경력 수치">
          <div><strong>4년+</strong><span>실무 경력</span></div>
          <div><strong>6곳</strong><span>제조 현장 시스템</span></div>
          <div><strong>5개</strong><span>FEMS 모듈<br />1인 설계</span></div>
        </section>

        <section>
          <SectionLabel>EDUCATION</SectionLabel>
          <p className="single-line">한국방송통신대학교 컴퓨터과학과 · 재학 <span>(2022.03–)</span></p>
        </section>

        <section>
          <SectionLabel>CERTIFICATES</SectionLabel>
          <div className="certificate-list">
            {certificates.map(([name, date]) => (
              <div className="certificate-row" key={name}>
                <span>{name}</span>
                <i />
                <time>{date}</time>
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionLabel>CAREER</SectionLabel>
          <div className="timeline">
            {careers.map((career) => (
              <article className="timeline-item" key={career.period}>
                <time>{career.period}</time>
                <h3>{career.company}</h3>
                <p>{career.role}</p>
                <strong>{career.result}</strong>
              </article>
            ))}
          </div>
        </section>

        <section>
          <SectionLabel>AWARDS</SectionLabel>
          <div className="award">
            <time>2026.10</time>
            <p>기후테크 넷제로 스케일업상<br /><span>경기창조경제혁신센터</span></p>
          </div>
        </section>

        <a className="studio-card" href="https://eip.hyudo.kr" target="_blank" rel="noreferrer">
          <span className="studio-label">FACTORY STUDIO</span>
          <h2>Factory Studio</h2>
          <p>제조 업무를 눌러보며 이해하는 통합 플랫폼</p>
          <strong>eip.hyudo.kr →</strong>
        </a>
      </div>

      <footer>
        <Monogram size={24} color="#1A1C1E" />
        <p className="footer-wordmark">H Y U D O</p>
        <div className="footer-links">
          <a href="mailto:go8105@gmail.com" aria-label="이메일 보내기"><MailIcon /></a>
          <span />
          <a href="https://github.com/go8105" target="_blank" rel="noreferrer" aria-label="GitHub"><GithubIcon /></a>
        </div>
        <small>© 2026 Hwang Kyoungho</small>
      </footer>
    </main>
  );
}
