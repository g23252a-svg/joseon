#!/usr/bin/env node
/* ================================================================
   동아 — 헤드리스 시뮬레이터
   ----------------------------------------------------------------
   index.html 안의 놀이 논리를 그림 없이 돌린다.
   규칙을 고칠 때마다 "정말 이길 수도 질 수도 있는가"를 눈이 아니라
   숫자로 확인하기 위한 도구다.

     node tools/sim.mjs                 — 기본 세 가지 두는 법을 각 3판씩
     node tools/sim.mjs --runs 5        — 판 수를 바꾼다
     node tools/sim.mjs --plan good     — 한 가지 두는 법만
     node tools/sim.mjs --seed 7        — 씨앗을 고정한다
     node tools/sim.mjs --trace         — 해마다 한 줄씩 찍는다
     node tools/sim.mjs --diff 0        — 난이도 (0 순한맛 · 1 보통 · 2 매운맛)
   ================================================================ */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/* ---------------------------------------------------------------- 인자 */
const argv = process.argv.slice(2);
function arg(name, def){
  const i = argv.indexOf('--' + name);
  if(i < 0) return def;
  const v = argv[i+1];
  return (v === undefined || v.startsWith('--')) ? true : v;
}
const RUNS  = +arg('runs', 3);
const PLAN  = arg('plan', null);
const SEED  = arg('seed', null);
const TRACE = !!arg('trace', false);
const QUIET = !!arg('quiet', false);
const DIFF  = arg('diff', null);      // 0 순한맛 / 1 보통 / 2 매운맛

/* ---------------------------------------------------------------- 난수 */
/* Math.random을 갈아 끼워 같은 씨앗이면 같은 판이 나오게 한다 */
function mulberry32(a){
  return function(){
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------------------------------------------------------------- 껍데기 */
/* 캔버스가 하는 일은 전부 삼킨다. 그림은 이 도구의 관심이 아니다. */
function noopCanvasContext(){
  const handler = {
    get(t, k){
      if(k === 'canvas') return t.__canvas;
      if(k === 'measureText') return () => ({ width: 10 });
      if(k === 'isPointInPath' || k === 'isPointInStroke') return () => false;
      if(k === 'createLinearGradient' || k === 'createRadialGradient')
        return () => ({ addColorStop(){} });
      if(k === 'getImageData') return (x, y, w, h) => ({ data: new Uint8ClampedArray(w*h*4) });
      if(k in t) return t[k];
      return () => {};
    },
    set(t, k, v){ t[k] = v; return true; }
  };
  return new Proxy({ __canvas: null }, handler);
}
function fakeCanvas(w, h){
  const c = {
    width: w || 1280, height: h || 720, style: {},
    getContext(){ return this.__ctx || (this.__ctx = noopCanvasContext()); },
    getBoundingClientRect(){ return { left:0, top:0, width:this.width, height:this.height }; },
    addEventListener(){}, removeEventListener(){},
    toDataURL(){ return ''; }
  };
  return c;
}
/* 캔버스 밖의 조각들 — 고을 선택 상자와 화면 읽기용 알림 */
function fakeElement(tag){
  return {
    tagName: (tag || 'div').toUpperCase(), style: {}, dataset: {}, children: [],
    hidden: false, value: '', textContent: '', disabled: false,
    addEventListener(){}, removeEventListener(){},
    appendChild(child){ this.children.push(child); return child; },
    setAttribute(){}, getAttribute(){ return null; },
    getBoundingClientRect(){ return { left:0, top:0, width:0, height:0 }; }
  };
}

function makeSandbox(rng){
  const store = new Map();
  const sandbox = {
    console,
    Math: Object.create(Math),
    Date, JSON, URLSearchParams, Object, Array, String, Number, Boolean,
    Set, Map, Error, parseInt, parseFloat, isNaN, isFinite,
    Uint8ClampedArray, Float64Array,
    innerWidth: 1280, innerHeight: 720,
    location: { search: '' },
    performance: { now: () => 0 },
    requestAnimationFrame(){ return 0; },
    cancelAnimationFrame(){},
    setTimeout(){ return 0; }, clearTimeout(){},
    addEventListener(){}, removeEventListener(){},
    localStorage: {
      getItem: k => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => { store.set(k, String(v)); },
      removeItem: k => { store.delete(k); },
      clear: () => store.clear()
    },
    document: {
      __els: {},
      getElementById(id){
        if(id === 'cv') return this.__cv || (this.__cv = fakeCanvas(1280, 720));
        return this.__els[id] || (this.__els[id] = fakeElement('div'));
      },
      createElement(tag){ return tag === 'canvas' ? fakeCanvas(1, 1) : fakeElement(tag); }
    },
    Image: class { constructor(){ this.width = 0; this.height = 0; }
                   set src(v){ this._src = v; } get src(){ return this._src; } },
    Path2D: class { constructor(){} addPath(){} moveTo(){} lineTo(){} closePath(){} },
    __store: store
  };
  sandbox.Math.random = rng;
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.self = sandbox;
  return sandbox;
}

/* ---------------------------------------------------------------- 적재 */
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const geo  = fs.readFileSync(path.join(ROOT, 'assets/map_geo.js'), 'utf8');

/* index.html 안의 인라인 <script>만 뽑는다 (src=... 는 건너뛴다) */
function inlineScripts(src){
  const out = [];
  const re = /<script([^>]*)>([\s\S]*?)<\/script>/g;
  let m;
  while((m = re.exec(src))){
    if(/\bsrc\s*=/.test(m[1])) continue;
    out.push(m[2]);
  }
  return out;
}
const SCRIPTS = inlineScripts(html);
if(!SCRIPTS.length) throw new Error('index.html에서 인라인 script를 찾지 못했습니다.');

/* 같은 문(script) 안에 붙여야 const 로 선언된 것들이 보인다 */
const EPILOGUE = `
;globalThis.__GET = function(__n){ return eval(__n); };
;globalThis.__CALL = function(__n, __a){ return eval(__n).apply(null, __a || []); };
;globalThis.__EVAL = function(__s){ return eval(__s); };
`;

function boot(seed){
  const rng = mulberry32(seed);
  const sandbox = makeSandbox(rng);
  const ctx = vm.createContext(sandbox);
  vm.runInContext(geo, ctx, { filename: 'assets/map_geo.js' });
  SCRIPTS.forEach((s, i) => {
    vm.runInContext(s + (i === SCRIPTS.length - 1 ? EPILOGUE : ''), ctx,
      { filename: 'index.html#script' + i });
  });
  const get  = n => sandbox.__GET(n);
  const call = (n, ...a) => sandbox.__CALL(n, a);
  const ev   = s => sandbox.__EVAL(s);
  if(DIFF != null) ev('START_DIFF=' + (+DIFF));    // 난이도를 고른 뒤에 판을 연다
  return { sandbox, get, call, ev, rng };
}

/* ---------------------------------------------------------------- 화면 점검 */
/* 그림은 검사하지 않는다. 다만 모든 화면이 터지지 않고 한 번은 그려져야 한다.
   캔버스에 대고 그리는 일은 전부 삼키므로, 남는 것은 순수한 논리 오류뿐이다. */
function uiCheck(){
  const api = boot(4242);
  let fail = 0, ran = 0;
  /* 화면 크기를 바꿔 가며 본다 — 손전화 판이 생긴 뒤로는 한 벌만 봐서는 모른다 */
  const 화면 = (w,h) => { api.sandbox.innerWidth=w; api.sandbox.innerHeight=h; api.call('resize'); };
  const shot = (label, setup) => {
    try{
      setup();
      api.call('draw');
      ran++;
    }catch(e){
      fail++;
      console.error(`✗ 화면 「${label}」 — ${e.message}\n${(e.stack||'').split('\n').slice(0,4).join('\n')}`);
    }
  };

  api.call('newGame');
  const G = api.get('G');

  shot('제목', () => api.ev("SCENE='title'; MENU=null;"));
  shot('제목 · 불러오기', () => api.ev("SCENE='title'; MENU={tab:'load', from:'title'};"));
  shot('제목 · 기록', () => api.ev("SCENE='title'; MENU={tab:'records', from:'title'};"));

  const TABS = api.get('TABS');
  TABS.forEach(t => shot('놀이 · ' + t, () => {
    api.ev("SCENE='play'; MENU=null;");
    G.tab = t; G.popup = null; G.report = null;
  }));
  /* 고을을 고른 상태 — 아래 판의 명령줄이 그려진다 */
  TABS.forEach(t => shot('놀이 · ' + t + ' · 고을 선택', () => {
    api.ev("SCENE='play'; MENU=null;");
    G.tab = t; G.sel = 'hans'; G.popup = null; G.report = null;
  }));
  shot('놀이 · 남의 고을 선택 (침공 미리보기)', () => {
    api.ev("SCENE='play'; MENU=null;");
    G.sel = 'liao'; G.popup = null; G.report = null;
  });
  shot('놀이 · 민심 보기', () => { G.view = 'unrest'; });
  shot('놀이 · 정치 지도', () => { G.mapMode = 'political'; G.view = 'nat'; });
  shot('놀이 · 동아시아 전체', () => api.call('setMapPreset', 'all'));
  shot('놀이 · 한반도 확대', () => api.call('setMapPreset', 'korea'));
  shot('놀이 · 최대로 당긴 지도', () => {
    api.call('zoomAt', 8 + 888/2, 62 + 480/2, 99);   // 상한까지 당긴다
  });
  shot('놀이 · 끝까지 옮긴 지도', () => {
    G.mapPan.x = 1e6; G.mapPan.y = 1e6; api.call('clampPan');
  });

  /* 한 해를 넘긴 뒤의 창들 */
  api.call('endTurn');
  shot('결산', () => { api.ev("MENU=null;"); });
  shot('사건 선택지', () => {
    G.report = null;
    const EVENTS = api.get('EVENTS');
    G.popup = { kind:'choice', ev:EVENTS[0], y:G.year };
  });
  shot('사건 결과', () => {
    G.popup = { kind:'result', title:'시험', body:'시험 본문이다.', y:G.year };
  });
  shot('시대 알림', () => {
    G.popup = { kind:'era', title:'시험 시대', body:'시험 설명이다.', y:G.year };
  });
  shot('메뉴', () => { G.popup = null; api.ev("MENU={tab:null};"); });
  shot('저장 칸', () => api.ev("MENU={tab:'save'};"));
  shot('놀이 중 기록', () => api.ev("MENU={tab:'records'};"));
  shot('소리 설정', () => api.ev("MENU={tab:'sound'};"));
  shot('제목 · 소리 설정', () => api.ev("SCENE='title'; MENU={tab:'sound', from:'title'};"));
  shot('싸움 효과가 떠 있는 지도', () => {
    api.ev("SCENE='play'; MENU=null;");
    G.popup = null; G.report = null;
    api.call('fxBattle', G.provs['pyab'], G.provs['liao'], true, 1200, 3400);
    api.call('fxFlip', G.provs['jeon'], 'chn', '전라도 반란', '#c4534a');
    api.call('fxPop', 'hans', '개간', '#8fbf6a');
    api.call('fxTick', 0.3);
  });
  shot('확인 창', () => api.ev("MENU={confirm:{title:'시험',body:'시험',ok:'한다',fn:function(){}}};"));

  /* 외교·기술이 실제로 맺어진 상태에서도 그려져야 한다 */
  shot('외교 · 조약을 다 맺은 상태', () => {
    api.ev("MENU=null;");
    G.popup = null; G.tab = '외교';
    G.dip.chn.trade = true; G.dip.chn.ally = true; G.dip.chn.tribute = true;
    G.dip.jpn.war = true; G.dip.jpn.truce = 4;
  });
  shot('기술 · 마디를 여럿 연 상태', () => {
    G.tab = '기술';
    G.res.pt = 5000;
    ['sucha','sijeon','hwacha','jiphyeon'].forEach(id => { G.res.done[id] = 1500; });
  });
  shot('기록 없는 결말', () => {
    G.tab = '국정';
    G.popup = { kind:'end', title:'시험 결말', body:'시험', y:G.year, total:100, rank:1 };
  });

  /* 끝까지 간 판의 결말 화면 — 성적이 여덟 줄 쌓인 상태 */
  shot('여덟 시대 성적표', () => {
    for(let e = 0; e < 8; e++) api.call('scoreEra', e);
    G.popup = { kind:'end', title:'육백 년', body:'여기까지 왔다.', y:2025, total:900, rank:2 };
  });

  /* 세 가지 판 크기에서 모든 탭과 창을 한 번씩 */
  [[1280,720,'넓은 판'],[900,520,'좁은 판'],[390,844,'세로 판(손전화)']].forEach(([w,h,nm])=>{
    화면(w,h);
    shot(nm+' · 제목', () => api.ev("SCENE='title'; MENU=null;"));
    TABS.forEach(t => shot(nm+' · '+t, () => {
      api.ev("SCENE='play'; MENU=null;");
      G.tab=t; G.sel='hans'; G.popup=null; G.report=null;
    }));
    shot(nm+' · 고을 안 고름', () => { G.sel=null; });
    shot(nm+' · 남의 고을', () => { G.sel='liao'; });
    shot(nm+' · 결산', () => { api.call('endTurn'); });
    shot(nm+' · 사건', () => { G.report=null; G.popup={kind:'choice', ev:api.get('EVENTS')[0], y:G.year}; });
    shot(nm+' · 메뉴', () => { G.popup=null; api.ev("MENU={tab:null};"); });
    shot(nm+' · 소리', () => api.ev("MENU={tab:'sound'};"));
    shot(nm+' · 기록', () => api.ev("MENU={tab:'records'};"));
    shot(nm+' · 결말', () => { api.ev("MENU=null;");
      G.popup={kind:'end',title:'육백 년',body:'여기까지 왔다.',y:2025,total:900,rank:1}; });
  });
  화면(1280,720);

  console.log(fail ? `\n화면 점검 — ${ran}개 그림, ${fail}개 터짐`
                   : `화면 점검 — ${ran}개 화면 모두 그려짐`);
  return fail;
}

/* ---------------------------------------------------------------- 저장 점검 */
/* 저장했다가 불러왔을 때 사라지는 것이 없어야 한다.
   예전 판은 사건 이력·연구·외교를 흘렸고, 불러오면 조용히 처음으로 돌아가 있었다. */
function saveCheck(){
  const api = boot(777);
  api.call('newGame');
  const G = api.get('G');

  /* 판을 충분히 어지럽힌 뒤에 저장한다 */
  for(let i = 0; i < 60; i++){
    PLANS.good.play(api);
    api.call('endTurn');
    G.report = null;
    if(G.pendingEvent){ api.call('applyEffects', G.pendingEvent.c[0].e || {}); G.pendingEvent = null; }
    G.evQueue = [];
    if(G.popup && G.popup.kind !== 'end') G.popup = null;
  }
  G.dip.chn.trade = true; G.dip.chn.tribute = true;
  G.dip.jpn.war = true; G.dip.jpn.warYears = 2; G.dip.jpn.truce = 0;
  G.tab = '외교'; G.sel = 'jeon'; G.view = 'unrest'; G.byeol = 2;

  const before = snapshot(G);
  api.call('saveGame', '1');
  const ok = api.call('loadGame', '1');
  if(!ok){ console.error('✗ 불러오지 못했다'); return 1; }
  const after = snapshot(api.get('G'));

  let fail = 0;
  for(const k of Object.keys(before)){
    if(JSON.stringify(before[k]) !== JSON.stringify(after[k])){
      console.error(`✗ 저장에서 흘린 것 — ${k}\n   저장 전: ${JSON.stringify(before[k]).slice(0,140)}` +
                    `\n   불러온 뒤: ${JSON.stringify(after[k]).slice(0,140)}`);
      fail++;
    }
  }
  console.log(fail ? `저장 점검 — ${fail}가지가 사라졌다` : '저장 점검 — 저장하고 불러와도 그대로다');
  return fail;
}
function snapshot(G){
  return {
    year:G.year, era:G.era, turn:G.turn, legit:G.legit, byeol:G.byeol, saheWait:G.saheWait,
    tab:G.tab, sel:G.sel, view:G.view, mapMode:G.mapMode, mapFocus:G.mapFocus,
    mapZoom:G.mapZoom, mapPan:G.mapPan,
    policies:G.policies, polSince:G.polSince, factions:G.factions,
    scores:G.scores, evDone:G.evDone,
    '연구':{ pt:G.res.pt, done:G.res.done },
    '외교':G.dip,
    '이웃끼리':G.cj,
    '국고':G.nations.kor.gold, '식량':G.nations.kor.food, '기술':G.nations.kor.tech,
    '신하':G.officials.map(o=>o.nm+':'+o.post+':'+Math.round(o.loy)).sort(),
    '고을':Object.entries(G.provs).map(([k,p])=>
      [k,p.nat,p.pop,p.dev,p.farm,p.trade,p.fort,Math.round(p.unrest),p.army].join('/')).sort()
  };
}


/* ---------------------------------------------------------------- 두는 법 */
/* 사람이 두는 흉내를 낸다. 잘 두는 판과 못 두는 판이 실제로 갈리는지 본다. */

const PLANS = {
  /* 아무것도 하지 않는다 — 넘기기만 */
  idle: {
    nm: '넘기기만',
    play(){}
  },
  /* 수령만 챙긴다 */
  govern: {
    nm: '수령만',
    play(api){ api.call('autoAssign'); }
  },
  /* 수령·명령·정책·조정을 두루 챙긴다 */
  good: {
    nm: '두루 챙김',
    play(api){
      const G = api.get('G');
      const N = G.nations.kor;
      api.call('autoAssign');

      /* 정책 — 시대에 맞는 것을 셋까지 */
      const POLICIES = api.get('POLICIES');
      const want = ['nongbon','daedong','silhak','gaehwa','gyoyuk','suchul','yeongu','bokji'];
      for(const id of want){
        if(G.policies.length >= 3) break;
        if(G.policies.includes(id)) continue;
        const P = POLICIES.find(p => p.id === id);
        if(!P || G.era < P.era) continue;
        if(N.gold < P.cost * 2.2) continue;
        api.call('togglePolicy', P);
      }

      /* 명령 — 정무가 남는 동안 값이 싼 것부터 */
      const ACTIONS = api.get('ACTIONS');
      const natProvs = n => api.call('natProvs', n);
      let guard = 0;
      while((N.adm || 0) > 0 && guard++ < 40){
        const mine = natProvs('kor');
        if(!mine.length) break;
        /* 가장 어지러운 고을부터 달랜다 */
        const hot = mine.slice().sort((a,b) => b.unrest - a.unrest)[0];
        let did = false;
        const tryAct = (id, p) => {
          if(did) return;
          const a = ACTIONS.find(x => x.id === id);
          if(!a || !a.need(p)) return;
          if((N.adm || 0) < a.adm) return;
          const q = api.call('actQuote', a, p);
          if(!q.ok || N.gold < q.c * 1.5) return;
          api.call('pay', q, a.adm, () => a.run(p)); did = true;
        };
        if(hot.unrest > 45) tryAct('jin', hot);
        if(!did){
          /* 농지가 얕은 고을을 넓힌다 */
          const poor = mine.slice().sort((a,b) => a.farm - b.farm)[0];
          tryAct('gaegan', poor);
        }
        if(!did){
          const rich = mine.slice().sort((a,b) => b.pop - a.pop)[0];
          tryAct('sijang', rich);
        }
        if(!did){
          const weak = mine.slice().sort((a,b) => a.fort - b.fort)[0];
          tryAct('chuk', weak);
        }
        if(!did) break;
        api.call('recalc');
      }

      /* 기술 마디 — 열 수 있는 것이 있으면 연다. 가지를 고루 편다. */
      const TECHS = api.get('TECHS');
      for(const t of TECHS){
        if(G.res.done[t.id]) continue;
        if(!api.call('techOpen', t)) continue;
        if(G.res.pt < t.cost) continue;
        api.call('unlockTech', t);
      }

      /* 외교 — 사이를 벌려 두지 않는다. 통상은 열 수 있으면 연다. */
      const DIP_NATS = api.get('DIP_NATS');
      for(const k of DIP_NATS){
        const d = G.dip[k];
        if((N.adm || 0) <= 1) break;
        const acts = api.call('dipActs', k);
        const use = (id) => {
          const a = acts.find(x => x.id === id);
          if(!a || !a.can()) return false;
          if((N.adm || 0) < a.adm) return false;
          if(N.gold < a.cost * 2) return false;
          N.gold -= a.cost; N.adm -= a.adm; a.run();
          return true;
        };
        if(d.war){ use('peace'); continue; }
        if(!d.trade && d.rel >= 25){ if(use('trade')) continue; }
        if(!d.ally && d.rel >= 60){ if(use('ally')) continue; }
        if(d.rel < 20){ use('envoy'); }
      }

      /* 조정의 일 — 국고가 넉넉하면 기술과 명분을 민다 */
      const NATIONALS = api.get('NATIONALS');
      for(const a of NATIONALS){
        if((N.adm || 0) < a.adm) break;
        const c = api.call('natCost', a);
        if(N.gold < c * 3) continue;
        if(a.id === 'naetang' && N.stab > 70) continue;
        if(a.id === 'chobing' && G.pool.length > 4) continue;
        if(a.id === 'jongmyo' && G.legit > 78) continue;
        N.gold -= c; N.adm -= a.adm; a.run(); api.call('recalc');
      }
    }
  },
  /* 정복만 노린다 — 이길 만한 곳이 있으면 치고, 없으면 모병한다.
     "얼마나 빨리 다 먹을 수 있나"를 재기 위한 두는 법이다. */
  conquer: {
    nm: '정복',
    play(api){
      const G = api.get('G'), N = G.nations.kor;
      api.call('autoAssign');
      const ACTIONS = api.get('ACTIONS');
      const gong = ACTIONS.find(a => a.id === 'gong');
      const mo   = ACTIONS.find(a => a.id === 'mo');
      const jin  = ACTIONS.find(a => a.id === 'jin');
      let guard = 0;
      while((N.adm || 0) > 0 && guard++ < 30){
        /* 너무 어지러운 고을은 먼저 달랜다 — 반란으로 잃으면 손해다 */
        const hot = api.call('natProvs','kor').filter(p => p.unrest > 70).sort((a,b)=>b.unrest-a.unrest)[0];
        if(hot && (N.adm||0) >= jin.adm && jin.need(hot)){
          const c = api.call('actCost', jin, hot);
          if(N.gold >= c && N.food > hot.pop/240){
            N.gold -= c; N.adm -= jin.adm; jin.run(hot); api.call('recalc'); continue;
          }
        }
        /* 이길 낌새가 좋은 곳을 친다 */
        let best = null, bp = 0;
        Object.values(G.provs).forEach(p => {
          if(!gong.need(p)) return;
          const o = api.call('warOdds', p);
          if(o && o.p > bp){ bp = o.p; best = p; }
        });
        if(best && bp > 0.62){
          const q = api.call('actQuote', gong, best);
          if(q.ok){ api.call('pay', q, gong.adm, () => gong.run(best)); continue; }
        }
        /* 못 이길 것 같으면 군사를 불린다 */
        const mine = api.call('natProvs','kor').filter(p => mo.need(p)).sort((a,b)=>b.pop-a.pop);
        if(!mine.length || (N.adm||0) < mo.adm) break;
        const p = mine[0], q = api.call('actQuote', mo, p);
        if(!q.ok || N.gold < q.c * 1.2) break;
        api.call('pay', q, mo.adm, () => mo.run(p));
      }
    }
  },
  /* 밀어붙인다 — 사람이 작정하고 두는 흉내.
     정무를 다 쓰면 별칙으로 국고를 태우고, 이길 낌새가 반만 넘어도 친다.
     "얼마나 빨리 다 먹을 수 있나"의 상한을 재기 위한 두는 법이다. */
  rush: {
    nm: '밀어붙임',
    play(api){
      const G = api.get('G'), N = G.nations.kor;
      api.call('autoAssign');
      const ACTIONS = api.get('ACTIONS');
      const gong = ACTIONS.find(a => a.id === 'gong');
      const mo   = ACTIONS.find(a => a.id === 'mo');
      /* 정무가 남으면 정무로, 다 썼으면 별칙으로 — 화면의 규칙 그대로 */
      /* 화면이 쓰는 규칙을 그대로 쓴다 — 싸움은 별칙으로 살 수 없다 */
      const 지른다 = (act, p) => {
        const q = api.call('actQuote', act, p);
        if(!q.ok) return false;
        api.call('pay', q, act.adm, () => act.run(p));
        return true;
      };
      let guard = 0;
      while(guard++ < 60){
        let best = null, bp = 0;
        Object.values(G.provs).forEach(p => {
          if(!gong.need(p)) return;
          const o = api.call('warOdds', p);
          if(o && o.p > bp){ bp = o.p; best = p; }
        });
        if(best && bp > 0.50){ if(지른다(gong, best)) continue; }
        /* 못 이길 것 같으면 국경 고을에 군사를 몰아넣는다 */
        const 국경 = api.call('natProvs','kor')
          .filter(p => mo.need(p) && [...p.adj].some(id => G.provs[id] && G.provs[id].nat !== 'kor'))
          .sort((a,b) => b.pop - a.pop);
        const 대상 = 국경[0] || api.call('natProvs','kor').filter(p => mo.need(p)).sort((a,b)=>b.pop-a.pop)[0];
        if(!대상) break;
        if(!지른다(mo, 대상)) break;
      }
    }
  },
  /* 외교만 챙긴다 — 이웃을 달래는 것만으로 얼마나 버티는지 */
  envoy: {
    nm: '외교만',
    play(api){
      const G = api.get('G'), N = G.nations.kor;
      api.call('autoAssign');
      for(const k of api.get('DIP_NATS')){
        const d = G.dip[k];
        const acts = api.call('dipActs', k);
        const use = (id) => {
          const a = acts.find(x => x.id === id);
          if(!a || !a.can() || (N.adm || 0) < a.adm || N.gold < a.cost * 2) return false;
          N.gold -= a.cost; N.adm -= a.adm; a.run();
          return true;
        };
        if(d.war){ use('peace'); continue; }
        if(!d.trade && d.rel >= 25){ if(use('trade')) continue; }
        if(d.rel < 30) use('envoy');
      }
    }
  },
  /* 이간 — 남을 붙여 놓고 그 틈에 민다.
     '밀어붙임'과 같은 손을 쓰되, 이웃끼리 손을 잡으려 하면 먼저 벌려 놓는다.
     새로 놓은 층에 정말 대응할 수 있는지, 그 값이 되는지를 재기 위한 두는 법이다. */
  wedge: {
    nm: '이간질',
    play(api){
      const G = api.get('G'), N = G.nations.kor, C = G.cj;
      /* 이웃이 손을 잡을 낌새면 먼저 벌린다 — 명령보다 앞선다 */
      if(C){
        const a = api.call('cjActs').find(x => x.id === 'wedge');
        if(a && a.can() && (N.adm||0) >= a.adm && N.gold >= a.cost*2 && C.rel > -30){
          N.gold -= a.cost; N.adm -= a.adm; a.run();
        }
      }
      PLANS.rush.play(api);
    }
  }
};

/* 사건 선택 — 효과 합이 가장 큰 갈래를 고른다 (사람의 '적당히 잘 두기') */
function pickChoice(ev, mood){
  let best = 0, bs = -1e9;
  ev.c.forEach((c, i) => {
    let s = 0;
    for(const [k, v] of Object.entries(c.e || {})){
      const w = { stab:1.4, legitimacy:1.1, tech:1.0, army:0.7, gold:0.6, food:0.6 }[k] || 0.5;
      s += v * w;
    }
    if(mood === 'worst') s = -s;
    if(s > bs){ bs = s; best = i; }
  });
  return best;
}

/* ---------------------------------------------------------------- 한 판 */
function runOne(planKey, seed){
  const api = boot(seed);
  const plan = PLANS[planKey];
  api.call('newGame');
  const G = api.get('G');
  const trace = [];

  let year = G.year, guard = 0;
  /* 언제 얼마나 먹었는지 — 정복이 너무 쉬운지 재는 눈금 */
  let peak = 0, y30 = null, yAll = null;
  /* 이웃끼리의 사이 — 명과 일본이 서로 얼마나 붙고 얼마나 손을 잡는지.
     조선만 보는 눈으로는 이 층이 도는지 알 수가 없다. */
  let cjWars = 0, cjWarY = 0, cjAllyY = 0, cjWas = false, cjFirst = null;
  while(!G.ended && G.year < 2025 && guard++ < 900){
    try { plan.play(api); }
    catch(e){ return { err: '두는 중 오류: ' + e.message + '\n' + e.stack, year: G.year }; }

    try { api.call('endTurn'); }
    catch(e){ return { err: '한 해 넘김 오류: ' + e.message + '\n' + e.stack, year: G.year }; }

    /* 결산과 사건을 사람 대신 넘긴다 */
    G.report = null;
    if(G.pendingEvent){
      const ev = G.pendingEvent;
      const i = pickChoice(ev, planKey === 'idle' ? 'worst' : 'best');
      api.call('applyEffects', ev.c[i].e || {});
      G.pendingEvent = null;
    }
    if(G.popup && G.popup.kind !== 'end') G.popup = null;

    const C = G.cj;
    if(C){
      if(C.war){ cjWarY++; if(!cjWas){ cjWars++; if(cjFirst==null) cjFirst=G.year; } }
      cjWas = C.war;
      if(C.ally) cjAllyY++;
    }
    const np = api.call('natProvs','kor').length;
    if(np > peak) peak = np;
    if(y30 === null && np >= 30) y30 = G.year;
    if(yAll === null && np >= Object.keys(G.provs).length) yAll = G.year;

    if(TRACE && G.year % 25 === 0){
      const N = G.nations.kor;
      trace.push(`${G.year}  고을 ${api.call('natProvs','kor').length}  국고 ${Math.round(N.gold)}` +
                 `  곡식 ${Math.round(N.food)}  민심 ${Math.round(N.stab)}  기술 ${N.tech.toFixed(0)}` +
                 `  인구 ${Math.round(N.pop/10000)}만`);
    }
    year = G.year;
  }

  const N = G.nations.kor;
  const total = G.scores.reduce((a, s) => a + s.pt, 0);
  return {
    year, total, peak, y30, yAll, cjWars, cjWarY, cjAllyY, cjFirst,
    scores: G.scores.map(s => `${s.era} ${s.pt}(${s.등급})`),
    prov: api.call('natProvs','kor').length,
    ended: !!G.ended,
    how: G.popup && G.popup.kind === 'end' ? G.popup.title : (G.year >= 2025 ? '완주' : '중단'),
    stab: Math.round(N.stab), tech: Math.round(N.tech), pop: N.pop, gold: Math.round(N.gold),
    trace
  };
}

/* ---------------------------------------------------------------- 본체 */
/* 점검 모드는 PLANS가 선 뒤에 부른다 — 저장 점검이 '두루 챙김'을 쓴다 */
if(arg('ui', false))   process.exit(uiCheck() ? 1 : 0);
if(arg('save', false)) process.exit(saveCheck() ? 1 : 0);

const keys = PLAN ? [PLAN] : Object.keys(PLANS);
for(const k of keys){
  if(!PLANS[k]){ console.error('모르는 두는 법: ' + k); process.exit(2); }
}

let bad = 0;
const summary = [];
for(const k of keys){
  const rows = [];
  for(let i = 0; i < RUNS; i++){
    const seed = SEED != null ? (+SEED + i) : (1000 + i * 7919);
    const r = runOne(k, seed);
    if(r.err){
      console.error(`✗ ${PLANS[k].nm} (씨앗 ${seed}) — ${r.year}년에서 터짐\n${r.err}`);
      bad++;
      continue;
    }
    rows.push(r);
    if(!QUIET){
      console.log(`${PLANS[k].nm.padEnd(8)} 씨앗 ${String(seed).padEnd(6)} → ` +
        `${String(r.year).padStart(4)}년 ${r.how.padEnd(10)} ` +
        `합계 ${String(r.total).padStart(5)}점  고을 ${String(r.prov).padStart(2)}  ` +
        `최대 ${String(r.peak).padStart(2)}  ` +
        `30고을 ${String(r.y30 ?? '—').padStart(4)}  전부 ${String(r.yAll ?? '—').padStart(4)}`);
      if(TRACE) r.trace.forEach(t => console.log('    ' + t));
    }
  }
  if(rows.length){
    const avg = a => Math.round(rows.reduce((s, r) => s + a(r), 0) / rows.length);
    const got30 = rows.filter(r => r.y30 != null);
    summary.push({
      nm: PLANS[k].nm,
      year: avg(r => r.year), total: avg(r => r.total), prov: avg(r => r.prov),
      peak: avg(r => r.peak),
      y30: got30.length ? Math.round(got30.reduce((s,r)=>s+r.y30,0)/got30.length) + '년' : '—',
      done: rows.filter(r => r.year >= 2025).length + '/' + rows.length,
      cjWars: avg(r => r.cjWars), cjWarY: avg(r => r.cjWarY), cjAllyY: avg(r => r.cjAllyY)
    });
  }
}

console.log('\n── 요약 ──' + (DIFF!=null? '  (난이도 '+['순한맛','보통','매운맛'][+DIFF]+')' : ''));
console.log('두는 법        평균 끝난 해   평균 점수   평균 고을   최대 고을   30고을   완주');
summary.forEach(s => {
  console.log(`${s.nm.padEnd(12)} ${String(s.year).padStart(8)} ${String(s.total).padStart(11)} ` +
              `${String(s.prov).padStart(11)} ${String(s.peak).padStart(11)} ` +
              `${String(s.y30).padStart(8)} ${s.done.padStart(7)}`);
});

/* 이웃끼리 — 이 층이 실제로 도는지 */
console.log('\n── 명과 일본 사이 ──');
console.log('두는 법        서로 전쟁(번)   전쟁으로 보낸 해   서로 동맹한 해');
summary.forEach(s => {
  console.log(`${s.nm.padEnd(12)} ${String(s.cjWars).padStart(10)} ` +
              `${String(s.cjWarY).padStart(15)} ${String(s.cjAllyY).padStart(14)}`);
});

if(bad){ console.error(`\n${bad}판이 터졌다.`); process.exit(1); }
