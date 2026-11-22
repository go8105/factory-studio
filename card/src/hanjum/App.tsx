import { useState, type ReactNode } from 'react'

type IconName = 'soap' | 'bag' | 'reuse' | 'press' | 'twist' | 'drawer'

const situations: { icon: IconName; title: string; text: string }[] = [
  { icon: 'soap', title: '공용 비누가 망설여질 때', text: '내 비누를 내 손으로 덜어 씁니다.' },
  { icon: 'bag', title: '여행·캠핑 짐을 줄일 때', text: '액체 용기 대신 고체 비누 하나.' },
  { icon: 'reuse', title: '얇아진 비누 조각', text: '버리지 않고 끝까지 갈아 씁니다.' },
]

const steps: { icon: IconName; number: string; title: string; text: string }[] = [
  { icon: 'press', number: '01', title: '누르기', text: '부드러운 외피를 눌러 비누를 붙잡습니다.' },
  { icon: 'twist', number: '02', title: '비틀기', text: '살짝 비틀면 비누가 곱게 갈립니다.' },
  { icon: 'drawer', number: '03', title: '덜어 쓰기', text: '가루통을 빼서 필요한 만큼 덜어 씁니다.' },
]

const details = [
  ['PALM SIZE', '손바닥 크기'],
  ['SOFT TOUCH', '주름 외피의 부드러운 손맛'],
  ['PULL-OUT TRAY', '통째로 빠지는 가루통'],
  ['OPEN & REFILL', '뚜껑을 열어 비누 교체'],
]

const scenes = ['여행', '캠핑', '헬스장', '사무실']

const faqs = ['어떤 비누를 쓰나요?', '세척은 어떻게 하나요?', '언제 살 수 있나요?', '대량·협업 문의는?']

function Monogram({ size = 30 }: { size?: number }) {
  return (
    <svg className="monogram" aria-label="HD" width={size * 1.15} height={size} viewBox="0 0 46 40" fill="none">
      <path d="M4 4V36M4 20H24M24 4V36M24 4H29C37.3 4 42 10.7 42 20C42 29.3 37.3 36 29 36H24" stroke="currentColor" strokeWidth="1.5" />
      <path d="M29 20H36M33 17L36 20L33 23" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
    </svg>
  )
}

function LineIcon({ name }: { name: IconName }) {
  const common = {
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.5,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }
  return (
    <svg className="line-icon" viewBox="0 0 48 48" aria-hidden="true">
      {name === 'soap' && (
        <>
          <rect x="10" y="16" width="28" height="20" rx="6" {...common} />
          <path d="M16 23c4-3 12-3 16 0M18 29h12" {...common} />
        </>
      )}
      {name === 'bag' && (
        <>
          <path d="M12 18h24l-2 20H14l-2-20Z" {...common} />
          <path d="M18 19v-3a6 6 0 0 1 12 0v3M20 29l3 3 6-7" {...common} />
        </>
      )}
      {name === 'reuse' && (
        <>
          <path d="M18 12h12l5 8M35 20l-1-7M35 20l-7-1M35 29l-6 8h-9M20 37l5 3M20 37l2-7M13 29l-3-9 5-8M10 20l-4-3M10 20l7 1" {...common} />
        </>
      )}
      {name === 'press' && (
        <>
          <path d="M14 11v10M10 17l4 4 4-4M34 11v10M30 17l4 4 4-4" {...common} />
          <rect x="10" y="25" width="28" height="14" rx="5" {...common} />
          <path d="M16 25v14M32 25v14" {...common} />
        </>
      )}
      {name === 'twist' && (
        <>
          <rect x="11" y="16" width="26" height="20" rx="6" {...common} />
          <path d="M8 14c4-5 11-7 17-6M8 14l1-7M8 14l7-1M40 38c-4 4-11 5-17 3M40 38l-1 7M40 38l-7 1" {...common} />
        </>
      )}
      {name === 'drawer' && (
        <>
          <path d="M12 11h24v16H12zM16 27v10h24V21h-4M25 32h6" {...common} />
          <path d="M9 32h7M12 29l-3 3 3 3" {...common} />
        </>
      )}
    </svg>
  )
}

function ProductDrawing() {
  return (
    <div className="product-stage" aria-label="한줌 제품 이미지 자리">
      <span className="prototype-badge">시제품 개발 중</span>
      {/* shortcut: v3 설계 렌더, 실물 사진이 오면 card/public/images/soap-grinder.jpg 교체 */}
      <img className="product-photo" src="/images/soap-grinder.jpg" alt="한줌 휴대용 비누 그라인더" />
      <div className="stage-caption"><span>86</span><i /><span>106</span><i /><span>46 mm</span></div>
    </div>
  )
}

function ExplodedView() {
  const layers = [
    ['①', '부드러운 덮개', '뚜껑을 열어 비누를 넣습니다'],
    ['②', '주름 외피', '눌렀다 놓으면 다시 펴집니다'],
    ['③', '그라인딩 모듈', '비누를 가는 부분'],
    ['④', '가루통', '통째로 빠집니다'],
  ]
  return (
    <div className="exploded">
      <svg className="exploded-art" viewBox="0 0 360 500" aria-label="한줌 분해도 일러스트">
        <g fill="none" stroke="#8D9194" strokeWidth="1.5">
          <rect x="64" y="40" width="194" height="58" rx="22" fill="#F7F7F6" />
          <rect x="54" y="150" width="214" height="84" rx="26" fill="#F2F0E9" />
          <path d="M70 171c20-7 36-7 55 0s36 7 55 0 36-7 72 1M65 197c20-7 39-7 60 0s36 7 55 0 36-7 77 1" />
          <rect x="69" y="287" width="184" height="42" rx="15" fill="#F7F7F6" />
          <rect x="55" y="390" width="212" height="66" rx="16" fill="#F7F7F6" />
          <path d="M130 420h62" />
          <path d="M268 68h48M270 192h46M254 308h62M268 423h48" stroke="#C7C8C6" />
        </g>
      </svg>
      <div className="exploded-labels">
        {layers.map(([number, title, text]) => (
          <div className="exploded-label" key={number}>
            <span>{number}</span>
            <p><strong>{title}</strong><small>{text}</small></p>
          </div>
        ))}
      </div>
    </div>
  )
}

function SectionHeading({ eyebrow, children, align = 'left' }: { eyebrow: string; children: ReactNode; align?: 'left' | 'center' }) {
  return (
    <div className={`section-heading ${align === 'center' ? 'center' : ''}`}>
      <span className="eyebrow">{eyebrow}</span>
      <h2>{children}</h2>
    </div>
  )
}

function App() {
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <main>
      <header className="topbar">
        <a className="brand-lockup" href="/" aria-label="HYUDO 홈"><Monogram /><span>HYUDO</span></a>
        <a className="maker-link" href="/">만든 사람</a>
      </header>

      <section className="hero shell">
        <div className="hero-visual"><ProductDrawing /></div>
        <div className="hero-copy">
          <span className="eyebrow">PORTABLE SOAP GRINDER</span>
          <h1>한줌</h1>
          <p className="hanjum-en">H A N J U M</p>
          <p className="hero-line">비누를, 한 줌만큼.</p>
          <p className="hero-description">누르고 비틀어 덜어 쓰는<br />휴대용 비누 그라인더</p>
          <div className="hero-actions">
            <a className="button primary" href="mailto:go8105@gmail.com?subject=%ED%95%9C%EC%A4%8C%20%EC%B6%9C%EC%8B%9C%20%EC%86%8C%EC%8B%9D">출시 소식 받기</a>
            <a className="text-link" href="#how">작동 방식 보기 <span>↓</span></a>
          </div>
        </div>
      </section>

      <section className="section shell situations">
        <SectionHeading eyebrow="FOR EVERYDAY">이럴 때, 한줌</SectionHeading>
        <div className="three-grid">
          {situations.map((item) => (
            <article className="plain-card" key={item.title}>
              <LineIcon name={item.icon} />
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section how-section" id="how">
        <div className="shell">
          <SectionHeading eyebrow="HOW IT WORKS" align="center">세 번의 간단한 동작</SectionHeading>
          <div className="steps-grid">
            {steps.map((step) => (
              <article className="step" key={step.number}>
                <div className="step-visual"><LineIcon name={step.icon} /></div>
                <div className="step-copy"><span>{step.number}</span><h3>{step.title}</h3><p>{step.text}</p></div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section inside shell">
        <SectionHeading eyebrow="INSIDE">펼쳐 본 한줌</SectionHeading>
        <ExplodedView />
      </section>

      <section className="section details shell">
        <SectionHeading eyebrow="DETAILS">작지만 분명한 쓰임</SectionHeading>
        <div className="detail-grid">
          {details.map(([label, title], index) => (
            <article className="detail-card" key={title}>
              <div className={`detail-image detail-${index + 1}`} aria-label={`${title} 이미지 자리`}>
                <div className="detail-object" />
              </div>
              <span>{label}</span><h3>{title}</h3>
            </article>
          ))}
        </div>
      </section>

      <section className="statement">
        <div className="statement-inner">
          <span>CARRY IT ACROSS</span>
          <p>생각에서 손끝까지.</p>
        </div>
      </section>

      <section className="section scenes shell">
        <SectionHeading eyebrow="WHEREVER YOU GO">어디서든, 내 비누</SectionHeading>
        <div className="scene-scroll">
          {scenes.map((scene, index) => (
            <article className={`scene-card scene-${index + 1}`} key={scene}>
              <div className="scene-placeholder"><span>{String(index + 1).padStart(2, '0')}</span></div>
              <h3>{scene}</h3>
            </article>
          ))}
        </div>
      </section>

      <section className="section info-section">
        <div className="shell info-grid">
          <div>
            <SectionHeading eyebrow="SPECIFICATION">시제품 사양</SectionHeading>
            <dl className="spec-table">
              <div><dt>크기</dt><dd>86×106×46mm</dd></div>
              <div><dt>구성</dt><dd>덮개·외피·그라인딩 모듈·가루통</dd></div>
              <div><dt>사용 비누</dt><dd>일반 고형 비누</dd></div>
              <div><dt>소재</dt><dd>검토 중</dd></div>
            </dl>
            <p className="note">시제품 기준, 최종 사양은 바뀔 수 있습니다</p>
          </div>
          <div>
            <SectionHeading eyebrow="MAKING PROCESS">만드는 과정</SectionHeading>
            <div className="timeline">
              {['3D 설계', '3D 프린팅 시제품', '실사용 테스트'].map((title, index) => (
                <article key={title}>
                  <div className="timeline-thumb"><span>0{index + 1}</span></div>
                  <p>{title}</p>
                </article>
              ))}
            </div>
            <span className="award-badge">모두의 창업 1라운드 합격</span>
          </div>
        </div>
      </section>

      <section className="section faq shell">
        <SectionHeading eyebrow="FAQ">자주 묻는 질문</SectionHeading>
        <div className="faq-list">
          {faqs.map((question, index) => {
            const open = openFaq === index
            return (
              <div className="faq-item" key={question}>
                <button type="button" onClick={() => setOpenFaq(open ? null : index)} aria-expanded={open}>
                  <span>{question}</span><i>{open ? '−' : '+'}</i>
                </button>
                {open && <p>자세한 내용은 출시 준비와 함께 안내드릴 예정입니다.</p>}
              </div>
            )
          })}
        </div>
      </section>

      <section className="final-cta" id="maker">
        <div className="final-cta-inner">
          <span className="eyebrow gold">STAY INFORMED</span>
          <h2>출시 소식을 가장 먼저<br />받아보세요.</h2>
          <a className="button gold-button" href="mailto:go8105@gmail.com?subject=%ED%95%9C%EC%A4%8C%20%EC%B6%9C%EC%8B%9C%20%EC%86%8C%EC%8B%9D">메일로 소식 받기</a>
          <p><a href="/">만든 사람 · www.hyudo.kr</a></p>
        </div>
      </section>

      <footer>
        <Monogram />
        <span>H Y U D O</span>
        <small>© 2026 HYUDO</small>
      </footer>
    </main>
  )
}

export default App
