import { chromium } from '../../../../frontend/node_modules/@playwright/test/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--use-angle=swiftshader','--enable-webgl']});
try {
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{
 window.SpeechRecognition=window.webkitSpeechRecognition=class {start(){window.testRecognition=this;this.onstart?.();}abort(){}}
 Object.defineProperty(window,'speechSynthesis',{value:{cancel(){},speak(u){setTimeout(()=>u.onend?.(),10)}}});
 window.SpeechSynthesisUtterance=class {constructor(t){this.text=t;}};
});
await page.goto((process.env.CAD_TEST_URL || 'http://127.0.0.1:5260/cad-cam-app/nc-review.html'));
await page.click('#voice-sample');
await page.waitForFunction(()=>document.querySelector('#voice-demo-status').textContent.includes('준비 완료'),{},{timeout:150000});
assert.match(await page.locator('#hugh-state').innerText(),/와이씨/);
assert.equal(await page.locator('dialog[open]').count(),0);
await page.locator('.proposal-panel').evaluate(el=>el.open=true);
await page.click('#proposal-run');
assert.equal(await page.locator('dialog[open]').count(),0);
async function speak(text){ await page.evaluate(t=>{
 const r=window.testRecognition; const result=[{transcript:t}];result.isFinal=true;
 r.onresult({resultIndex:0,results:[result]});
},text); await page.waitForTimeout(800); }
await speak('헤이 와이씨');
await speak('업로드한 파일 최적안 제안해줘');
assert.equal(await page.locator('dialog[open]').count(),1);
assert.equal(await page.locator('.stage-live').count(),0);
await speak('3번 실행해줘');
assert.equal(await page.locator('.stage-live canvas').count(),1);
await page.waitForTimeout(1000);
assert.equal(await page.locator('[data-stage-card]:visible').count(),1);
assert.equal(await page.locator('[data-stage-card="3"]:visible').count(),1);
assert.ok(await page.locator('#playback-progress').evaluate(el=>el.value)>0);
await page.screenshot({path:process.env.CAD_SCREENSHOT || '/tmp/cadv03-selected.png'});
await speak('멈춰');
await page.click('[data-stage-all]');
assert.equal(await page.locator('[data-stage-card]:visible').count(),3);
await page.click('[data-stage-close]');
await page.setViewportSize({width:390,height:844});
await page.waitForTimeout(100);
assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
await page.click('#voice-sample');
await page.locator('#source').fill('G21\nM30');
await page.waitForTimeout(500);
assert.match(await page.locator('#voice-demo-status').innerText(),/중단/);
assert.equal(await page.locator('#source').inputValue(),'G21\nM30');
await page.click('#voice-sample');
await page.waitForFunction(()=>document.querySelector('#voice-demo-status').textContent.includes('준비 완료'),{},{timeout:150000});
assert.equal(await page.locator('dialog[open]').count(),0);
assert.equal(errors.length,0,errors.join('\n'));
console.log('Demo auto-preparation, YC recognition event, silent step4, requested cards and number3 playback passed');
}finally {await browser.close()}
