<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Supreme Autos — Quality Vehicle Parts</title>
<meta name="description" content="Find the right replacement and performance parts for your exact vehicle. Search by vehicle or VIN.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preconnect" href="https://images.unsplash.com" crossorigin>
<link rel="preconnect" href="https://cdn.simpleicons.org" crossorigin>
<link rel="preconnect" href="https://flagcdn.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
/* ============================ DESIGN SYSTEM ============================ */
:root{
  --navy:#0B1E3B; --navy-700:#122a4d; --navy-600:#1c3a63; --navy-800:#081627;
  --red:#E01F26; --red-600:#c3151b; --red-tint:#FFF1F2;
  --white:#FFFFFF; --offwhite:#F6F7F9; --pale-navy:#EEF2F7;
  --line:#E2E6EC; --ink:#111827; --muted:#667085; --faint:#98a2b3;
  --ok:#12844a; --ok-tint:#e7f4ee; --warn:#b06a08; --warn-tint:#fbf1de; --oos:#98a2b3;
  --r-sm:10px; --r:12px; --r-lg:16px; --r-pill:999px;
  --sp:8px;
  --sh-sm:0 1px 2px rgba(11,30,59,.05);
  --sh:0 4px 16px -6px rgba(11,30,59,.12), 0 1px 3px rgba(11,30,59,.06);
  --sh-lg:0 24px 60px -24px rgba(11,30,59,.28);
  --maxw:1280px;
  --ease:cubic-bezier(.4,0,.2,1);
  --ease-out:cubic-bezier(.22,1,.36,1);
  --grain:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  --f:"Manrope",system-ui,-apple-system,sans-serif;
  --f-mono:"JetBrains Mono",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:var(--f);background:var(--white);color:var(--ink);font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased;counter-reset:sec;text-rendering:optimizeLegibility}
.grain{position:absolute;inset:0;pointer-events:none;background:var(--grain);background-size:160px;opacity:.06;z-index:1}
a{color:inherit;text-decoration:none}
button{font-family:inherit;cursor:pointer;border:0;background:none;color:inherit}
img{display:block;max-width:100%}
ul{list-style:none}
:focus-visible{outline:2px solid var(--red);outline-offset:2px;border-radius:4px}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 24px}
.mono{font-family:var(--f-mono);font-variant-numeric:tabular-nums}
.num{font-variant-numeric:tabular-nums}
h1,h2,h3,h4{font-weight:800;letter-spacing:-.03em;line-height:1.06;color:var(--navy)}
.eyebrow{display:inline-flex;align-items:center;gap:10px;font-size:12px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--red)}
.eyebrow::before{content:"";width:26px;height:2px;background:var(--red);border-radius:2px}
.eyebrow.on-navy{color:#ff8a8f}.eyebrow.on-navy::before{background:var(--red)}
/* auto-numbered section kicker (mono index) — signals a deliberate sequence, not a template */
.sec .eyebrow{counter-increment:sec}
.sec .eyebrow::after{content:"/ 0" counter(sec);font-family:var(--f-mono);font-weight:600;font-size:11px;letter-spacing:.02em;color:var(--faint);text-transform:none}
.hl{box-shadow:inset 0 -.11em 0 rgba(224,31,38,.92);padding-bottom:.01em}
/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:11px;height:48px;padding:0 20px;border-radius:var(--r-sm);font-weight:700;font-size:14.5px;transition:transform .3s var(--ease-out),background .25s var(--ease),box-shadow .3s var(--ease),border-color .2s var(--ease);white-space:nowrap}
/* nested arrow-chip: the icon lives in its own circle, flush to the button's right edge */
.btn .ar{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;margin-right:-4px;transition:transform .35s var(--ease-out),background .25s}
.btn .ar svg{width:14px;height:14px}
.btn-red .ar,.btn-navy .ar,.btn-ghost-light .ar{background:rgba(255,255,255,.18)}
.btn-outline .ar{background:var(--pale-navy)}
.btn:hover .ar{transform:translate(3px,-1px) scale(1.05)}
.btn:active{transform:translateY(1px) scale(.985)}
.btn-red{background:var(--red);color:#fff}
.btn-red:hover{background:var(--red-600);box-shadow:0 10px 24px -10px rgba(224,31,38,.5)}
.btn-navy{background:var(--navy);color:#fff}
.btn-navy:hover{background:var(--navy-700)}
.btn-outline{border:1.5px solid var(--line);color:var(--navy);background:#fff}
.btn-outline:hover{border-color:var(--navy);background:var(--offwhite)}
.btn-ghost-light{border:1.5px solid rgba(255,255,255,.3);color:#fff}
.btn-ghost-light:hover{border-color:#fff;background:rgba(255,255,255,.08)}
.btn-block{width:100%}
/* form controls */
.field label,.fld > label{display:block;font-size:12.5px;font-weight:600;color:var(--navy);margin-bottom:6px}
.control{width:100%;height:48px;border:1.5px solid var(--line);border-radius:var(--r-sm);background:#fff;color:var(--ink);padding:0 14px;font-family:var(--f);font-size:14.5px;font-weight:500;transition:border-color .2s,background .2s,box-shadow .2s}
.control:focus{outline:none;border-color:var(--navy);box-shadow:0 0 0 3px rgba(11,30,59,.08)}
.control:disabled{background:var(--offwhite);color:var(--faint);cursor:not-allowed;border-style:dashed}
select.control{appearance:none;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='none' stroke='%23667085' stroke-width='1.8' viewBox='0 0 24 24'><path d='m6 9 6 6 6-6'/></svg>");background-repeat:no-repeat;background-position:right 13px center;padding-right:36px}
.help-link{font-size:12.5px;color:var(--navy);font-weight:600;border-bottom:1px solid var(--line);transition:border-color .2s}
.help-link:hover{border-color:var(--navy)}
/* card */
.card{background:#fff;border:1px solid var(--line);border-radius:var(--r-lg);box-shadow:var(--sh-sm)}
/* reveal */
.reveal{opacity:0;transform:translateY(24px);filter:blur(5px);transition:opacity .8s var(--ease-out),transform .8s var(--ease-out),filter .8s var(--ease-out)}
.reveal.in{opacity:1;transform:none;filter:none}
@media (prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;filter:none;transition:none}*{scroll-behavior:auto!important}}
.sec{padding:96px 0}
.sec-head{max-width:660px;margin-bottom:52px}
.sec-head .eyebrow{margin-bottom:16px}
.sec-head h2{font-size:clamp(30px,3.6vw,44px);margin-top:0}
.sec-head p{color:var(--muted);font-size:16.5px;margin-top:15px;max-width:56ch}

/* ============================ UTILITY BAR ============================ */
.util{background:var(--navy-800);color:#a9b8d0;font-size:12.5px;border-bottom:1px solid rgba(255,255,255,.06)}
.util .wrap{display:flex;align-items:center;gap:22px;height:40px}
.util a{color:#a9b8d0;display:inline-flex;align-items:center;gap:6px;transition:color .2s}
.util a:hover{color:#fff}
.util .sp{flex:1}
.util .accent{color:#fff;font-weight:600}
.util svg{opacity:.85}
.util .usp{display:inline-flex;align-items:center;gap:6px}
/* ============================ HEADER ============================ */
.hdr{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:60;transition:box-shadow .3s var(--ease)}
.hdr.stuck{box-shadow:0 6px 24px -14px rgba(11,30,59,.25)}
.hdr .wrap{display:flex;align-items:center;gap:16px;height:72px}
.logo{display:flex;align-items:center;gap:11px;flex:0 0 auto}
.logo .mk{width:40px;height:40px}
.logo b{font-size:19px;font-weight:800;letter-spacing:-.03em;color:var(--navy);line-height:1;display:block}
.logo span{font-size:9.5px;letter-spacing:.22em;color:var(--muted);font-weight:600;display:block;margin-top:3px}
.mainnav{display:flex;gap:1px;margin-left:2px}
.mainnav a{position:relative;font-size:14.5px;font-weight:600;color:var(--ink);padding:9px 11px;border-radius:8px;white-space:nowrap;transition:color .2s,background .2s}
.mainnav a::after{content:"";position:absolute;left:11px;right:11px;bottom:4px;height:2px;background:var(--red);border-radius:2px;transform:scaleX(0);transform-origin:left;transition:transform .25s var(--ease)}
.mainnav a:hover{color:var(--navy)}
.mainnav a:hover::after,.mainnav a.on::after{transform:scaleX(1)}
.mainnav a.on{color:var(--navy)}
.hdr .sp{flex:1}
.hdr-icons{display:flex;align-items:center;gap:1px}
.iconbtn{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;color:var(--navy);position:relative;transition:background .2s}
.iconbtn:hover{background:var(--offwhite)}
.iconbtn .badge{position:absolute;top:6px;right:6px;background:var(--red);color:#fff;font-size:10px;font-weight:700;min-width:17px;height:17px;border-radius:9px;display:grid;place-items:center;padding:0 4px;font-family:var(--f-mono)}
.find-btn{margin-left:8px}
.burger{display:none;width:44px;height:44px;border-radius:10px;place-items:center;color:var(--navy)}
@media (max-width:1180px){.find-btn{display:none}}
@media (max-width:1080px){.hdr-icons .iconbtn[aria-label="Wishlist"],.hdr-icons .iconbtn[aria-label="Search"]{display:none}}

/* ============================ HERO ============================ */
.hero{position:relative;background:var(--navy);overflow:hidden}
.hero .bg{position:absolute;inset:0;z-index:0}
.hero .bg img{width:100%;height:100%;object-fit:cover;object-position:center 35%}
.hero .bg::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(8,22,40,.94) 0%,rgba(8,22,40,.82) 42%,rgba(11,30,59,.55) 100%)}
.hero .grid-tex{position:absolute;inset:0;z-index:1;opacity:.5;pointer-events:none;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:56px 56px}
.hero .wrap{position:relative;z-index:2;display:grid;grid-template-columns:1fr 448px;gap:48px;align-items:center;padding:72px 24px}
.hero-copy{color:#fff;max-width:560px}
.hero-copy h1{color:#fff;font-size:clamp(38px,4.9vw,58px);letter-spacing:-.038em;margin:22px 0 20px;line-height:1.02}
.hero-copy p{color:#c3cee0;font-size:17.5px;max-width:46ch;margin-bottom:30px}
.hero-cta{display:flex;gap:12px;flex-wrap:wrap}
.hero-trust{display:flex;align-items:center;gap:10px;margin-top:26px;color:#9fb0cc;font-size:13px;font-weight:500}
.hero-trust b{color:#fff;font-weight:600}
.hero-trust .dot{width:4px;height:4px;border-radius:50%;background:var(--red)}
/* search card */
.searchshell{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.14);border-radius:calc(var(--r-lg) + 7px);padding:7px;box-shadow:var(--sh-lg),inset 0 1px 0 rgba(255,255,255,.16)}
.searchcard{background:#fff;border-radius:var(--r-lg);box-shadow:0 1px 2px rgba(11,30,59,.12);overflow:hidden}
.tabs{display:flex;border-bottom:1px solid var(--line)}
.tab{flex:1;position:relative;height:56px;font-weight:700;font-size:14.5px;color:var(--muted);display:flex;align-items:center;justify-content:center;gap:8px;transition:color .2s}
.tab .ti{opacity:.7}
.tab.on{color:var(--navy)}
.tab.on::after{content:"";position:absolute;left:20px;right:20px;bottom:0;height:3px;background:var(--red);border-radius:3px 3px 0 0}
.tab:hover:not(.on){color:var(--navy)}
.tabbody{padding:22px}
.tabhead{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.tabhead h3{font-size:16px;font-weight:800}
.tabhead .live{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--ok)}
.tabhead .live .d{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 3px var(--ok-tint)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}
.fld{position:relative}
.recent{display:flex;align-items:center;gap:10px;background:var(--pale-navy);border-radius:var(--r-sm);padding:10px 12px;margin-bottom:14px;font-size:12.5px;color:var(--navy)}
.recent .ic{width:28px;height:20px;border-radius:5px;background:#fff;display:grid;place-items:center;color:var(--navy);flex:0 0 auto}
.recent b{font-weight:700}.recent .go{margin-left:auto;color:var(--red);font-weight:700}
.savegarage{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--muted);margin-top:12px;cursor:pointer}
.savegarage input{width:17px;height:17px;accent-color:var(--red)}
.vinnote{display:flex;align-items:flex-start;gap:9px;background:var(--pale-navy);border-radius:var(--r-sm);padding:11px 12px;font-size:12.5px;color:var(--navy-600);margin-top:14px;line-height:1.45}
.vinnote svg{flex:0 0 auto;margin-top:1px;color:var(--navy)}
.msg{font-size:12.5px;font-weight:600;margin-top:10px;display:none;align-items:center;gap:7px}
.msg.err{color:var(--red);display:flex}
.msg.ok{color:var(--ok);display:flex}

/* ============================ TRUST STRIP ============================ */
.trust{border-bottom:1px solid var(--line);background:#fff;counter-reset:tb}
.trust .wrap{display:grid;grid-template-columns:repeat(4,1fr);gap:0}
.trust .b{position:relative;counter-increment:tb;display:flex;align-items:flex-start;gap:15px;padding:30px 30px 30px 26px;border-right:1px solid var(--line)}
.trust .b::before{content:"0" counter(tb);position:absolute;top:18px;right:22px;font-family:var(--f-mono);font-size:11px;font-weight:600;color:var(--faint);letter-spacing:.02em}
.trust .b:last-child{border-right:0}
.trust .b .ic{width:42px;height:42px;border-radius:50%;background:#fff;border:1px solid var(--line);box-shadow:inset 0 0 0 4px var(--offwhite);display:grid;place-items:center;color:var(--navy);flex:0 0 auto;transition:box-shadow .3s var(--ease-out),border-color .3s}
.trust .b:hover .ic{border-color:var(--red);box-shadow:inset 0 0 0 4px var(--red-tint)}
.trust .b b{display:block;font-size:15px;font-weight:800;color:var(--navy);letter-spacing:-.01em;margin-bottom:3px}
.trust .b span{font-size:12.5px;color:var(--muted);line-height:1.45;display:block;max-width:20ch}

/* ============================ CATALOG ============================ */
.catalog{background:var(--offwhite)}
.cat-search{position:relative;max-width:520px;margin-top:22px}
.cat-search .control{height:52px;padding-left:44px}
.cat-search svg{position:absolute;left:15px;top:16px;color:var(--muted)}
.catpanel{position:relative;margin-top:28px;background:#fff;border:1px solid var(--line);border-radius:var(--r-lg);box-shadow:var(--sh);overflow:hidden}
.catpanel::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--red) 0 22%,var(--navy) 22% 100%);opacity:.9;z-index:3}
.breadcrumb{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:16px 20px;border-bottom:1px solid var(--line);background:var(--pale-navy)}
.breadcrumb .crumbs{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:13.5px;font-weight:600;color:var(--navy)}
.breadcrumb .crumbs .step{display:inline-flex;align-items:center;gap:8px}
.breadcrumb .crumbs .ph{color:var(--faint);font-weight:500}
.breadcrumb .crumbs .sep{color:var(--faint)}
.breadcrumb .sp{flex:1}
.breadcrumb .act{display:flex;gap:8px;align-items:center}
.breadcrumb .txtbtn{font-size:13px;font-weight:600;color:var(--muted);padding:8px 10px;border-radius:8px;transition:color .2s,background .2s}
.breadcrumb .txtbtn:hover{color:var(--navy);background:#fff}
.breadcrumb .btn{height:40px;padding:0 16px;font-size:13.5px}
.cols{display:grid;grid-template-columns:repeat(5,1fr)}
.col{border-right:1px solid var(--line);min-width:0;display:flex;flex-direction:column}
.col:last-child{border-right:0}
.col .ch{padding:14px 16px 10px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:700;display:flex;align-items:center;justify-content:space-between}
.col .ch .n{color:var(--faint);font-family:var(--f-mono);font-size:11px}
.col .filt{position:relative;padding:0 12px 10px}
.col .filt input{width:100%;height:34px;border:1px solid var(--line);border-radius:8px;padding:0 10px 0 30px;font-size:12.5px;font-family:var(--f);background:var(--offwhite)}
.col .filt input:focus{outline:none;border-color:var(--navy);background:#fff}
.col .filt svg{position:absolute;left:22px;top:9px;color:var(--faint)}
.col .list{overflow-y:auto;max-height:320px;padding:2px 8px 10px}
.col .list::-webkit-scrollbar{width:8px}.col .list::-webkit-scrollbar-thumb{background:var(--line);border-radius:8px}
.opt{position:relative;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 11px;border-radius:8px;font-size:13.5px;font-weight:500;color:var(--ink);cursor:pointer;transition:background .15s,color .15s}
.opt:hover{background:var(--offwhite)}
.opt .n{font-family:var(--f-mono);font-size:11.5px;color:var(--faint)}
.opt .cv{color:var(--faint);flex:0 0 auto}
.opt .opt-l{display:inline-flex;align-items:center;gap:7px;min-width:0}
.opt .flags{display:inline-flex;align-items:center;gap:3px;flex:0 0 auto}
.opt .flag{height:11px;width:auto;display:block;border-radius:2px;box-shadow:0 0 0 1px rgba(11,30,59,.14)}
.opt.on{background:var(--pale-navy);color:var(--navy);font-weight:700}
.opt.on::before{content:"";position:absolute;left:0;top:6px;bottom:6px;width:3px;border-radius:3px;background:var(--red)}
.opt.on .n{color:var(--navy-600)}
.popular{padding:16px 20px;border-top:1px solid var(--line);display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.popular .lbl{font-size:12.5px;font-weight:700;color:var(--muted)}
.chipv{display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 13px;border:1px solid var(--line);border-radius:var(--r-pill);font-size:13px;font-weight:600;color:var(--navy);background:#fff;transition:border-color .2s,background .2s}
.chipv:hover{border-color:var(--navy);background:var(--offwhite)}
.chipv svg{color:var(--muted)}
/* mobile catalog accordion */
.mcat{display:none;margin-top:22px}
.mstep{background:#fff;border:1px solid var(--line);border-radius:var(--r);margin-bottom:10px;overflow:hidden}
.mstep .mh{display:flex;align-items:center;gap:12px;padding:16px;width:100%;text-align:left;font-weight:700;color:var(--navy)}
.mstep .mh .num{width:26px;height:26px;border-radius:50%;background:var(--pale-navy);color:var(--navy);font-size:12px;font-weight:700;display:grid;place-items:center;flex:0 0 auto}
.mstep.done .mh .num{background:var(--red);color:#fff}
.mstep .mh .val{margin-left:auto;font-size:13px;color:var(--muted);font-weight:600}
.mstep .mh .cv{transition:transform .3s var(--ease)}
.mstep.open .mh .cv{transform:rotate(180deg)}
.mstep .mb{max-height:0;overflow:hidden;transition:max-height .35s var(--ease)}
.mstep.open .mb{max-height:340px;overflow-y:auto}
.mstep .mb .opt{margin:0 12px}
.mstep[aria-disabled="true"]{opacity:.5}

/* ============================ MARQUEE ============================ */
.brands{padding:56px 0;background:#fff;border-bottom:1px solid var(--line)}
.brands h2{text-align:center;font-size:16px;font-weight:700;color:var(--muted);letter-spacing:-.01em;margin-bottom:30px}
.marquee{position:relative;overflow:hidden;-webkit-mask-image:linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent);mask-image:linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent)}
.marquee .track{display:flex;gap:64px;width:max-content;animation:scroll 42s linear infinite}
.marquee:hover .track{animation-play-state:paused}
.marquee .lg{height:34px;display:grid;place-items:center;flex:0 0 auto}
.marquee .lg img{height:30px;width:auto;opacity:.55;filter:saturate(0);transition:opacity .3s,filter .3s}
.marquee .lg:hover img{opacity:1;filter:none}
@keyframes scroll{to{transform:translateX(calc(-50% - 32px))}}
@media (prefers-reduced-motion:reduce){.marquee .track{animation:none;flex-wrap:wrap;justify-content:center;width:auto;gap:40px 56px}.marquee{-webkit-mask-image:none;mask-image:none}}

/* ============================ CATEGORIES ============================ */
.cats{background:var(--offwhite)}
.cats .sec-head{display:flex;justify-content:space-between;align-items:flex-end;max-width:none;gap:24px}
.cats .sec-head .l{max-width:560px}
.catgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.ccard{position:relative;background:#fff;border:1px solid var(--line);border-radius:var(--r-lg);overflow:hidden;display:flex;flex-direction:column;transition:transform .3s var(--ease),box-shadow .3s var(--ease),border-color .3s}
.ccard:hover{transform:translateY(-4px);box-shadow:var(--sh);border-color:#d3dae4}
.ccard .im{position:relative;aspect-ratio:5/4;background:linear-gradient(160deg,#fff,var(--offwhite));display:grid;place-items:center;padding:22px;border-bottom:1px solid var(--line)}
.ccard .im::after{content:"";position:absolute;left:0;right:0;bottom:0;height:22%;background:linear-gradient(transparent,var(--offwhite));pointer-events:none}
.ccard .im img{max-width:82%;max-height:82%;object-fit:contain;mix-blend-mode:multiply;transition:transform .4s var(--ease)}
.ccard:hover .im img{transform:scale(1.06)}
.ccard .bd{padding:16px 18px;display:flex;align-items:center;gap:12px}
.ccard .bd .t{flex:1;min-width:0}
.ccard .bd b{display:block;font-size:15.5px;font-weight:700;color:var(--navy);letter-spacing:-.01em}
.ccard .bd span{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.ccard .arw{width:36px;height:36px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;color:var(--navy);flex:0 0 auto;transition:.25s var(--ease)}
.ccard:hover .arw{background:var(--red);border-color:var(--red);color:#fff}
.ccard.feat{grid-column:span 2;grid-row:span 2}
.ccard.feat .im{aspect-ratio:auto;flex:1;padding:34px}
.ccard.feat .bd b{font-size:19px}
.ccard.feat::before{content:"Featured";position:absolute;top:16px;left:16px;z-index:2;font-family:var(--f-mono);font-size:10px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:#fff;background:var(--red);padding:6px 11px;border-radius:var(--r-pill);box-shadow:0 6px 16px -6px rgba(224,31,38,.55)}
.ccard.wide{grid-column:span 2}
.ccard.wide{flex-direction:row}
.ccard.wide .im{aspect-ratio:auto;width:150px;border-bottom:0;border-right:1px solid var(--line);flex:0 0 auto}
.ccard.wide .bd{flex:1}
.cats-cta{text-align:center;margin-top:36px}

/* ============================ FAQ ============================ */
.faq .wrap{display:grid;grid-template-columns:380px 1fr;gap:56px;align-items:start}
.faq .sec-head{margin-bottom:24px}
.support{background:var(--navy);color:#fff;border-radius:var(--r-lg);padding:24px;margin-top:8px}
.support b{font-size:16px;font-weight:800;color:#fff;display:block;margin-bottom:14px}
.support .ln{display:flex;align-items:center;gap:11px;padding:9px 0;color:#c3cee0;font-size:14px}
.support .ln svg{color:#ff8a8f;flex:0 0 auto}
.support .ln b{font-size:14px;margin:0;color:#fff;font-weight:600}
.support .btn{margin-top:16px}
.acc{display:flex;flex-direction:column;gap:10px}
.acc-item{border:1px solid var(--line);border-radius:var(--r);background:#fff;overflow:hidden;transition:border-color .2s,box-shadow .2s}
.acc-item.open{border-color:#d3dae4;box-shadow:var(--sh-sm)}
.acc-q{width:100%;display:flex;align-items:center;gap:16px;padding:18px 20px;text-align:left;font-size:15.5px;font-weight:700;color:var(--navy)}
.acc-q .ico{width:26px;height:26px;border-radius:50%;background:var(--pale-navy);color:var(--navy);display:grid;place-items:center;flex:0 0 auto;position:relative;transition:background .25s,color .25s}
.acc-item.open .acc-q .ico{background:var(--red);color:#fff}
.acc-q .ico i{position:absolute;background:currentColor;border-radius:2px;transition:transform .3s var(--ease),opacity .3s}
.acc-q .ico i.h{width:11px;height:2px}.acc-q .ico i.v{width:2px;height:11px}
.acc-item.open .acc-q .ico i.v{transform:rotate(90deg);opacity:0}
.acc-a{max-height:0;overflow:hidden;transition:max-height .35s var(--ease)}
.acc-a .inner{padding:0 20px 20px;color:var(--muted);font-size:14.5px;line-height:1.65;max-width:62ch}

/* ============================ NEWSLETTER ============================ */
.news{background:var(--navy);color:#fff;position:relative;overflow:hidden}
.news .blueprint{position:absolute;inset:0;opacity:.14;pointer-events:none;background-image:radial-gradient(circle at 82% 30%,rgba(224,31,38,.5),transparent 40%),linear-gradient(rgba(255,255,255,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.06) 1px,transparent 1px);background-size:auto,44px 44px,44px 44px}
.news .wrap{position:relative;z-index:2;display:grid;grid-template-columns:1fr 420px;gap:50px;align-items:center;padding:80px 24px}
.news h2{color:#fff;font-size:clamp(26px,3vw,36px);margin:16px 0 14px}
.news p{color:#b7c3d8;font-size:16px;max-width:44ch}
.news form{margin-top:26px;max-width:480px}
.news .row{display:flex;gap:12px}
.news input[type=email]{flex:1;height:52px;border-radius:var(--r-sm);border:1.5px solid rgba(255,255,255,.16);background:rgba(255,255,255,.06);color:#fff;padding:0 16px;font-family:var(--f);font-size:14.5px}
.news input[type=email]::placeholder{color:#8595b0}
.news input[type=email]:focus{outline:none;border-color:var(--red);background:rgba(255,255,255,.1)}
.news .btn{height:52px}
.news .chk{display:flex;align-items:center;gap:9px;margin-top:14px;font-size:13px;color:#9fb0cc;cursor:pointer}
.news .chk input{width:16px;height:16px;accent-color:var(--red)}
.news .priv{font-size:12.5px;color:#8595b0;margin-top:12px;display:flex;align-items:center;gap:7px}
.news .art{aspect-ratio:4/3;border-radius:var(--r-lg);overflow:hidden;border:1px solid rgba(255,255,255,.1)}
.news .art img{width:100%;height:100%;object-fit:cover}

/* ============================ FOOTER ============================ */
footer{background:var(--navy-800);color:#a9b8d0}
.ftop{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr 1fr;gap:36px;padding:60px 0 44px;border-bottom:1px solid rgba(255,255,255,.08)}
.fbrand .logo b{color:#fff}.fbrand .logo span{color:#7f90ac}
.fbrand p{font-size:14px;color:#8fa0bd;max-width:30ch;margin:16px 0}
.fcontact{display:flex;flex-direction:column;gap:9px;font-size:13.5px}
.fcontact .ln{display:flex;align-items:center;gap:9px}.fcontact svg{color:#ff8a8f;flex:0 0 auto}
.fsocial{display:flex;gap:9px;margin-top:16px}
.fsocial a{width:38px;height:38px;border-radius:9px;border:1px solid rgba(255,255,255,.12);display:grid;place-items:center;color:#a9b8d0;transition:.2s}
.fsocial a:hover{background:var(--red);border-color:var(--red);color:#fff}
footer h5{color:#fff;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:16px;font-weight:700}
footer .fcol ul{display:flex;flex-direction:column;gap:11px;font-size:14px}
footer .fcol a{color:#a9b8d0;transition:color .2s}
footer .fcol a:hover{color:#fff}
.fdivider{height:2px;background:linear-gradient(90deg,var(--red),transparent 40%)}
.fbase{display:flex;align-items:center;gap:20px;flex-wrap:wrap;padding:22px 0;font-size:12.5px;color:#7f90ac}
.fbase .sp{flex:1}
.fpay{display:flex;gap:8px}
.fpay span{height:26px;padding:0 9px;background:rgba(255,255,255,.9);border-radius:5px;display:grid;place-items:center;color:var(--navy);font-weight:800;font-size:9px}
.fcurrency{height:36px;border:1px solid rgba(255,255,255,.14);border-radius:8px;background:transparent;color:#a9b8d0;padding:0 30px 0 12px;font-family:var(--f);font-size:12.5px;appearance:none;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='none' stroke='%23a9b8d0' stroke-width='1.8' viewBox='0 0 24 24'><path d='m6 9 6 6 6-6'/></svg>");background-repeat:no-repeat;background-position:right 10px center}
.totop{position:fixed;right:24px;bottom:24px;width:46px;height:46px;border-radius:12px;background:var(--navy);color:#fff;display:grid;place-items:center;box-shadow:var(--sh-lg);opacity:0;transform:translateY(12px);pointer-events:none;transition:.3s var(--ease);z-index:70}
.totop.show{opacity:1;transform:none;pointer-events:auto}
.totop:hover{background:var(--red)}

/* ============================ MOBILE DRAWER ============================ */
.drawer-ov{position:fixed;inset:0;background:rgba(8,22,40,.5);opacity:0;pointer-events:none;transition:opacity .3s;z-index:80}
.drawer-ov.show{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(340px,86vw);background:#fff;transform:translateX(100%);transition:transform .35s var(--ease);z-index:81;display:flex;flex-direction:column;box-shadow:var(--sh-lg)}
.drawer.show{transform:none}
.drawer .dh{display:flex;align-items:center;justify-content:space-between;padding:18px 20px;border-bottom:1px solid var(--line)}
.drawer nav{padding:12px}
.drawer nav a{display:flex;align-items:center;justify-content:space-between;padding:14px;border-radius:10px;font-weight:600;color:var(--navy);font-size:16px}
.drawer nav a:hover{background:var(--offwhite)}
.drawer .df{margin-top:auto;padding:16px 20px;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:10px}

/* ============================ RESPONSIVE ============================ */
@media (max-width:1024px){
  .hero .wrap{grid-template-columns:1fr;gap:32px}
  .searchshell{max-width:534px}
  .faq .wrap{grid-template-columns:1fr;gap:32px}
  .news .wrap{grid-template-columns:1fr}.news .art{display:none}
  .catgrid{grid-template-columns:repeat(2,1fr)}
  .ccard.feat,.ccard.wide{grid-column:span 2;grid-row:auto}.ccard.feat .im{aspect-ratio:5/4}
  .ftop{grid-template-columns:1fr 1fr 1fr}.fbrand{grid-column:span 3}
}
@media (max-width:900px){
  .mainnav,.util .hidem{display:none}
  .burger{display:grid}
  .find-btn{display:none}
  .catpanel{display:none}.mcat{display:block}
  .trust .wrap{grid-template-columns:1fr 1fr}.trust .b:nth-child(2){border-right:0}.trust .b{border-bottom:1px solid var(--line)}
}
@media (max-width:560px){
  .wrap{padding:0 18px}.sec{padding:56px 0}
  .hero .wrap{padding:48px 18px}
  .hero-cta .btn{flex:1}
  .grid2{grid-template-columns:1fr}
  .cats .sec-head{flex-direction:column;align-items:flex-start;gap:20px}
  .catgrid{grid-template-columns:1fr}.ccard.feat,.ccard.wide{grid-column:span 1}.ccard.wide{flex-direction:column}.ccard.wide .im{width:auto;border-right:0;border-bottom:1px solid var(--line)}
  .trust .wrap{grid-template-columns:1fr}.trust .b{border-right:0}
  .ftop{grid-template-columns:1fr 1fr}.fbrand{grid-column:span 2}
  .news .row{flex-direction:column}.news .btn{width:100%}
  .totop{right:16px;bottom:16px}
}
</style>
<noscript><style>.reveal{opacity:1!important;transform:none!important;filter:none!important}</style></noscript>
</head>
<body>

<!-- ===== UTILITY BAR ===== -->
<div class="util"><div class="wrap">
  <span class="hidem usp"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M4 13a8 8 0 0 1 16 0M8 21a4 4 0 0 1-4-4v-3M20 14v3a4 4 0 0 1-4 4"/></svg>Need help finding a part?</span>
  <a class="hidem" href="tel:+18005550110"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M5 4h4l2 5-3 2a12 12 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg><span class="accent">1-800-555-0110</span></a>
  <a class="hidem" href="mailto:parts@supremeautos.com"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>parts@supremeautos.com</a>
  <span class="sp"></span>
  <span class="hidem usp"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M3 7h11v8H3zM14 10h4l3 3v2h-7z"/><circle cx="7.5" cy="18" r="1.5"/><circle cx="17.5" cy="18" r="1.5"/></svg>Free shipping over $99</span>
  <a href="#">Track Order</a>
  <a href="#"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>Sign In</a>
</div></div>

<!-- ===== HEADER ===== -->
<header class="hdr" id="hdr"><div class="wrap">
  <a class="logo" href="#" aria-label="Supreme Autos home">
    <svg class="mk" viewBox="0 0 40 40" fill="none" aria-hidden="true"><rect width="40" height="40" rx="10" fill="#0B1E3B"/><path d="M11 26c1-6 4-9 7-9h4c3 0 6 3 7 9" stroke="#fff" stroke-width="2.3" stroke-linecap="round"/><path d="M20 8l3 5h-6l3-5Z" fill="#E01F26"/><circle cx="15" cy="27" r="3.4" fill="#fff"/><circle cx="25" cy="27" r="3.4" fill="#fff"/><circle cx="15" cy="27" r="1.4" fill="#0B1E3B"/><circle cx="25" cy="27" r="1.4" fill="#0B1E3B"/></svg>
    <span><b>SUPREME AUTOS</b><span>QUALITY VEHICLE PARTS</span></span>
  </a>
  <nav class="mainnav" aria-label="Primary">
    <a class="on" href="#" aria-current="page">Home</a>
    <a href="#catalog">Parts Catalog</a>
    <a href="#categories">Categories</a>
    <a href="#brands">Brands</a>
    <a href="#">About Us</a>
    <a href="#">Contact</a>
  </nav>
  <span class="sp"></span>
  <div class="hdr-icons">
    <button class="iconbtn" aria-label="Search"><svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg></button>
    <button class="iconbtn" aria-label="Account"><svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg></button>
    <button class="iconbtn" aria-label="Wishlist"><svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M12 21C5 15 3 11 3 8a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 3-2 7-9 13Z"/></svg></button>
    <a class="iconbtn" href="<?= e($base) ?>/cart" aria-label="Cart"><svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M6 6h15l-1.6 9H7.5z"/><circle cx="9.5" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M6 6 5 3H2"/></svg><?php if ($cartN > 0): ?><span class="badge"><?= (int) $cartN ?></span><?php endif; ?></a>
  </div>
  <a class="btn btn-red find-btn" href="#catalog"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg>Find Your Part</a>
  <button class="burger" id="burger" aria-label="Open menu" aria-expanded="false"><svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
</div></header>

<!-- ===== HERO ===== -->
<section class="hero">
  <div class="bg"><img src="https://images.unsplash.com/photo-1487754180451-c456f719a1fc?q=80&w=1900&auto=format&fit=crop" alt="Automotive workshop engine bay" fetchpriority="high"></div>
  <div class="grid-tex"></div>
  <div class="grain"></div>
  <div class="wrap">
    <div class="hero-copy reveal">
      <span class="eyebrow on-navy">Parts That Fit. Performance You Trust.</span>
      <h1>Find the <span class="hl">Right Parts</span> for Your Exact Vehicle</h1>
      <p>Search thousands of quality replacement and performance parts selected to match your exact vehicle.</p>
      <div class="hero-cta">
        <a class="btn btn-red" href="#catalog">Browse Parts Catalog <span class="ar"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></a>
        <a class="btn btn-ghost-light" href="#faq">Get Expert Help</a>
      </div>
      <div class="hero-trust"><b>Accurate fitment</b><span class="dot"></span><b>Trusted brands</b><span class="dot"></span><b>Nationwide delivery</b></div>
    </div>
    <div class="searchshell reveal" style="transition-delay:.08s"><div class="searchcard">
      <div class="tabs" role="tablist">
        <button class="tab on" id="tab-veh" role="tab" aria-selected="true" data-tab="veh"><svg class="ti" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M5 17h14M6 17l1.5-6h9L18 17M8 11l1-3h6l1 3"/><circle cx="8" cy="18" r="1.4"/><circle cx="16" cy="18" r="1.4"/></svg>Search by Vehicle</button>
        <button class="tab" id="tab-vin" role="tab" aria-selected="false" data-tab="vin"><svg class="ti" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><rect x="3" y="7" width="18" height="10" rx="2"/><path d="M7 11h.01M11 11h.01M15 11h6M7 14h10"/></svg>Search by VIN</button>
      </div>
      <!-- Vehicle tab -->
      <div class="tabbody" id="panel-veh" role="tabpanel" aria-labelledby="tab-veh">
        <div class="tabhead"><h3>Select your vehicle</h3><span class="live"><span class="d"></span>Live stock</span></div>
        <div class="recent"><span class="ic"><svg width="18" height="12" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 16"><path d="M2 12h20M4 12l1.5-6h13L20 12M7 6l1-2.5h8L17 6"/><circle cx="7" cy="13" r="1.2"/><circle cx="17" cy="13" r="1.2"/></svg></span><span>Recently viewed: <b>2020 Acura MDX 3.5L V6</b></span><a class="go" href="#catalog">Resume</a></div>
        <div class="grid2">
          <div class="fld"><label for="v-year">Year</label><select class="control" id="v-year"><option value="">Select year</option><option>2024</option><option>2023</option><option>2022</option><option>2021</option><option>2020</option></select></div>
          <div class="fld"><label for="v-make">Make</label><select class="control" id="v-make" disabled><option value="">Select make</option><option>Acura</option><option>Toyota</option><option>Honda</option><option>Ford</option></select></div>
        </div>
        <div class="grid2">
          <div class="fld"><label for="v-model">Model</label><select class="control" id="v-model" disabled><option value="">Select model</option><option>MDX</option><option>TLX</option><option>RDX</option></select></div>
          <div class="fld"><label for="v-engine">Engine / Trim</label><select class="control" id="v-engine" disabled><option value="">Select engine</option><option>3.5L V6</option><option>2.0L L4 Turbo</option></select></div>
        </div>
        <button class="btn btn-red btn-block" id="findParts">Find Compatible Parts <span class="ar"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></button>
        <div class="msg" id="veh-msg" role="alert"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v5m0 3h.01"/></svg>Please complete all four fields to continue.</div>
        <label class="savegarage"><input type="checkbox" id="save-garage">Save this vehicle to My Garage</label>
      </div>
      <!-- VIN tab -->
      <div class="tabbody" id="panel-vin" role="tabpanel" aria-labelledby="tab-vin" hidden>
        <div class="tabhead"><h3>Enter your VIN</h3></div>
        <div class="fld" style="margin-bottom:12px"><label for="vin-input">17-character VIN</label><input class="control mono" id="vin-input" maxlength="17" placeholder="1HGBH41JXMN109186" style="text-transform:uppercase;letter-spacing:.04em"></div>
        <div class="fld" style="margin-bottom:14px"><label for="plate-input">License plate <span style="color:var(--muted);font-weight:500">(optional)</span></label><input class="control mono" id="plate-input" placeholder="ABC-1234" style="text-transform:uppercase"></div>
        <button class="btn btn-red btn-block" id="searchVin">Search VIN <span class="ar"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></button>
        <div class="msg" id="vin-msg" role="alert"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v5m0 3h.01"/></svg>A VIN must be exactly 17 characters.</div>
        <div class="msg" id="vin-ok"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" viewBox="0 0 24 24"><path d="m5 13 4 4 10-11"/></svg><span>Vehicle identified — loading matching parts…</span></div>
        <div class="vinnote"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4m0-4h.01"/></svg><span>Your VIN is a 17-character code found on the driver-side dashboard, inside the door jamb, or on your registration. <a class="help-link" href="#" style="display:inline">Where can I find my VIN?</a></span></div>
      </div>
    </div></div>
  </div>
</section>

<!-- ===== TRUST STRIP ===== -->
<section class="trust"><div class="wrap">
  <div class="b reveal"><span class="ic"><svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/><path d="m9 12 2 2 4-4"/></svg></span><div><b>Guaranteed Fitment</b><span>Matched to your exact vehicle</span></div></div>
  <div class="b reveal" style="transition-delay:.05s"><span class="ic"><svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M12 3l2.4 5 5.6.6-4 4 1.2 5.4L12 20l-5.2 2 1.2-5.4-4-4 5.6-.6z"/></svg></span><div><b>Trusted Brands</b><span>OEM &amp; premium aftermarket</span></div></div>
  <div class="b reveal" style="transition-delay:.1s"><span class="ic"><svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg></span><div><b>Secure Ordering</b><span>Encrypted checkout, trusted pay</span></div></div>
  <div class="b reveal" style="transition-delay:.15s"><span class="ic"><svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-3.5-7.1M21 4v5h-5"/></svg></span><div><b>Fast Support</b><span>Real parts specialists on call</span></div></div>
</div></section>

<!-- ===== CATALOG ===== -->
<section class="catalog sec" id="catalog"><div class="wrap">
  <div class="sec-head reveal">
    <span class="eyebrow">Complete Vehicle Catalog</span>
    <h2>Browse Parts by Vehicle</h2>
    <p>Select your vehicle step by step to view parts engineered for the correct fit.</p>
    <div class="cat-search"><svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input class="control" placeholder="Search make, model, engine, category, or part…" aria-label="Search catalog"></div>
  </div>

  <!-- desktop 5-column browser -->
  <div class="catpanel reveal">
    <div class="breadcrumb">
      <div class="crumbs" id="crumbs">
        <span class="step" data-c="make"><span class="ph">Make</span></span><span class="sep">›</span>
        <span class="step" data-c="year"><span class="ph">Year</span></span><span class="sep">›</span>
        <span class="step" data-c="model"><span class="ph">Model</span></span><span class="sep">›</span>
        <span class="step" data-c="engine"><span class="ph">Engine</span></span><span class="sep">›</span>
        <span class="step" data-c="cat"><span class="ph">Category</span></span>
      </div>
      <span class="sp"></span>
      <div class="act">
        <button class="txtbtn" id="clearSel">Clear Selection</button>
        <button class="txtbtn">Save Vehicle</button>
        <button class="btn btn-red" id="viewMatch">View Matching Parts <span class="ar"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></button>
      </div>
    </div>
    <div class="cols" id="cols">
      <div class="col" data-col="make"><div class="ch">Make <span class="n">—</span></div><div class="filt"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input placeholder="Filter" aria-label="Filter makes"></div><div class="list"></div></div>
      <div class="col" data-col="year"><div class="ch">Year <span class="n">—</span></div><div class="filt"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input placeholder="Filter" aria-label="Filter years"></div><div class="list"></div></div>
      <div class="col" data-col="model"><div class="ch">Model <span class="n">—</span></div><div class="filt"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input placeholder="Filter" aria-label="Filter models"></div><div class="list">
        <div class="opt" data-v="MDX">MDX <span class="cv"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></span></div>
        <div class="opt" data-v="TLX">TLX <span class="cv"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></span></div>
        <div class="opt" data-v="RDX">RDX <span class="cv"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></span></div>
        <div class="opt" data-v="Integra">Integra <span class="cv"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></span></div>
      </div></div>
      <div class="col" data-col="engine"><div class="ch">Engine / Trim <span class="n">—</span></div><div class="filt"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input placeholder="Filter" aria-label="Filter engines"></div><div class="list">
        <div class="opt" data-v="3.5L V6">3.5L V6 <span class="cv"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></span></div>
        <div class="opt" data-v="2.0L L4 Turbo">2.0L L4 Turbo <span class="cv"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></span></div>
      </div></div>
      <div class="col" data-col="cat"><div class="ch">Part Category <span class="n">21</span></div><div class="filt"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input placeholder="Filter" aria-label="Filter categories"></div><div class="list">
        <div class="opt" data-v="Engine">Engine <span class="n">1.2k</span></div>
        <div class="opt" data-v="Brakes">Brakes <span class="n">312</span></div>
        <div class="opt" data-v="Suspension">Suspension <span class="n">486</span></div>
        <div class="opt" data-v="Steering">Steering <span class="n">140</span></div>
        <div class="opt" data-v="Electrical">Electrical <span class="n">540</span></div>
        <div class="opt" data-v="Cooling">Cooling <span class="n">228</span></div>
        <div class="opt" data-v="Filters">Filters <span class="n">212</span></div>
        <div class="opt" data-v="Transmission">Transmission <span class="n">176</span></div>
        <div class="opt" data-v="Body Parts">Body Parts <span class="n">390</span></div>
        <div class="opt" data-v="Lighting">Lighting <span class="n">168</span></div>
        <div class="opt" data-v="Interior">Interior <span class="n">120</span></div>
        <div class="opt" data-v="Wheels &amp; Tyres">Wheels &amp; Tyres <span class="n">94</span></div>
      </div></div>
    </div>
    <div class="popular">
      <span class="lbl">Popular Vehicles</span>
      <button class="chipv"><svg width="15" height="10" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 16"><path d="M2 12h20M4 12l1.5-6h13L20 12"/></svg>Toyota Corolla</button>
      <button class="chipv"><svg width="15" height="10" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 16"><path d="M2 12h20M4 12l1.5-6h13L20 12"/></svg>Honda Civic</button>
      <button class="chipv"><svg width="15" height="10" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 16"><path d="M2 12h20M4 12l1.5-6h13L20 12"/></svg>Nissan Altima</button>
      <button class="chipv"><svg width="15" height="10" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 16"><path d="M2 12h20M4 12l1.5-6h13L20 12"/></svg>Ford F-150</button>
      <button class="chipv"><svg width="15" height="10" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 16"><path d="M2 12h20M4 12l1.5-6h13L20 12"/></svg>BMW 3 Series</button>
      <button class="chipv"><svg width="15" height="10" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 16"><path d="M2 12h20M4 12l1.5-6h13L20 12"/></svg>Mercedes-Benz C-Class</button>
    </div>
  </div>

  <!-- mobile progressive accordion -->
  <div class="mcat" id="mcat">
    <div class="mstep open" data-step="year"><button class="mh"><span class="num">1</span>Select Year<span class="val"></span><span class="cv"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg></span></button><div class="mb"><div class="opt" data-v="2024">2024</div><div class="opt" data-v="2023">2023</div><div class="opt" data-v="2022">2022</div><div class="opt" data-v="2021">2021</div><div class="opt" data-v="2020">2020</div></div></div>
    <div class="mstep" data-step="make" aria-disabled="true"><button class="mh"><span class="num">2</span>Select Make<span class="val"></span><span class="cv"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg></span></button><div class="mb"><div class="opt" data-v="Toyota">Toyota</div><div class="opt" data-v="Honda">Honda</div><div class="opt" data-v="Acura">Acura</div><div class="opt" data-v="Ford">Ford</div></div></div>
    <div class="mstep" data-step="model" aria-disabled="true"><button class="mh"><span class="num">3</span>Select Model<span class="val"></span><span class="cv"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg></span></button><div class="mb"><div class="opt" data-v="MDX">MDX</div><div class="opt" data-v="TLX">TLX</div><div class="opt" data-v="RDX">RDX</div></div></div>
    <div class="mstep" data-step="engine" aria-disabled="true"><button class="mh"><span class="num">4</span>Select Engine<span class="val"></span><span class="cv"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg></span></button><div class="mb"><div class="opt" data-v="3.5L V6">3.5L V6</div><div class="opt" data-v="2.0L L4 Turbo">2.0L L4 Turbo</div></div></div>
    <div class="mstep" data-step="cat" aria-disabled="true"><button class="mh"><span class="num">5</span>Select Category<span class="val"></span><span class="cv"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg></span></button><div class="mb"><div class="opt" data-v="Brakes">Brakes</div><div class="opt" data-v="Engine">Engine</div><div class="opt" data-v="Suspension">Suspension</div><div class="opt" data-v="Filters">Filters</div></div></div>
    <button class="btn btn-red btn-block" style="margin-top:8px">View Matching Parts</button>
  </div>
</div></section>

<!-- ===== BRAND MARQUEE ===== -->
<section class="brands" id="brands">
  <h2>Parts for the Brands You Trust</h2>
  <div class="marquee"><div class="track" id="track">
    <!-- filled by JS (duplicated for seamless loop) -->
  </div></div>
</section>

<!-- ===== CATEGORIES ===== -->
<section class="cats sec" id="categories"><div class="wrap">
  <div class="sec-head reveal">
    <div class="l"><span class="eyebrow">Shop by Category</span><h2>Everything Your Vehicle Needs</h2><p>Browse replacement, maintenance, performance, and exterior components.</p></div>
    <a class="btn btn-outline" href="#">View All Categories <span class="ar"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></a>
  </div>
  <div class="catgrid reveal">
    <a class="ccard feat" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/23/22SD360__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Brake rotor and pad set" loading="lazy"></div><div class="bd"><div class="t"><b>Brakes</b><span>312 parts available</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
    <a class="ccard" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/1050/19610__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Engine component" loading="lazy"></div><div class="bd"><div class="t"><b>Engine Components</b><span>1,240 parts</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
    <a class="ccard" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/260/SE54190-Front__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Suspension strut" loading="lazy"></div><div class="bd"><div class="t"><b>Suspension</b><span>486 parts</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
    <a class="ccard" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/196/13439_1__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Filter" loading="lazy"></div><div class="bd"><div class="t"><b>Filters</b><span>212 parts</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
    <a class="ccard" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/191/ATF-DW1__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Cooling fluid" loading="lazy"></div><div class="bd"><div class="t"><b>Cooling System</b><span>228 parts</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
    <a class="ccard wide" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/17/EM-7085__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Electrical component" loading="lazy"></div><div class="bd"><div class="t"><b>Electrical</b><span>540 parts available</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
    <a class="ccard" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/154/TX253_Front__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Wheel and tyre" loading="lazy"></div><div class="bd"><div class="t"><b>Wheels &amp; Tyres</b><span>94 parts</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
    <a class="ccard" href="#"><div class="im"><img src="<?= e(img_url('/RockAuto/assets/parts/1138/24019-complete__ra_m.jpg')) ?>" onerror="this.style.opacity=.15" alt="Body part" loading="lazy"></div><div class="bd"><div class="t"><b>Body Parts</b><span>390 parts</span></div><span class="arw"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span></div></a>
  </div>
</div></section>

<!-- ===== FAQ ===== -->
<section class="faq sec" id="faq"><div class="wrap">
  <div>
    <div class="sec-head reveal"><span class="eyebrow">Customer Support</span><h2>Questions Before You Order?</h2><p>Find quick answers about vehicle compatibility, VIN searches, ordering, delivery, and returns.</p></div>
    <div class="support reveal"><b>Still need help?</b>
      <div class="ln"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M5 4h4l2 5-3 2a12 12 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg><b>1-800-555-0110</b></div>
      <div class="ln"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>parts@supremeautos.com</div>
      <a class="btn btn-red btn-block" href="#">Contact Our Parts Team</a>
    </div>
  </div>
  <div class="acc reveal" id="acc">
    <div class="acc-item open"><button class="acc-q" aria-expanded="true"><span class="ico"><i class="h"></i><i class="v"></i></span>How do I know whether a part fits my vehicle?</button><div class="acc-a"><div class="inner">Every part is matched to your exact year, make, model, and engine using verified ACES fitment data. Select your vehicle or enter your VIN, and you will only see parts confirmed to fit — backed by our fitment guarantee.</div></div></div>
    <div class="acc-item"><button class="acc-q" aria-expanded="false"><span class="ico"><i class="h"></i><i class="v"></i></span>Can I search using my vehicle's VIN?</button><div class="acc-a"><div class="inner">Yes. Enter your 17-character VIN in the VIN tab and we decode your exact vehicle automatically, then show the parts that fit it — no manual selection needed.</div></div></div>
    <div class="acc-item"><button class="acc-q" aria-expanded="false"><span class="ico"><i class="h"></i><i class="v"></i></span>Where can I find my VIN number?</button><div class="acc-a"><div class="inner">Your VIN appears on the lower driver-side corner of the windshield, inside the driver door jamb, and on your vehicle registration and insurance documents.</div></div></div>
    <div class="acc-item"><button class="acc-q" aria-expanded="false"><span class="ico"><i class="h"></i><i class="v"></i></span>Do you sell genuine OEM and aftermarket parts?</button><div class="acc-a"><div class="inner">Both. We stock genuine OEM components alongside premium aftermarket brands, so you can choose the exact balance of price and specification you need.</div></div></div>
    <div class="acc-item"><button class="acc-q" aria-expanded="false"><span class="ico"><i class="h"></i><i class="v"></i></span>How long does delivery take?</button><div class="acc-a"><div class="inner">In-stock orders placed before 4pm dispatch the same day, with standard nationwide delivery in 2–4 business days. Expedited options are available at checkout.</div></div></div>
    <div class="acc-item"><button class="acc-q" aria-expanded="false"><span class="ico"><i class="h"></i><i class="v"></i></span>Can I return a part if it does not fit?</button><div class="acc-a"><div class="inner">Yes. Unused parts in original packaging can be returned within 90 days. If a part does not fit despite matching your vehicle, we cover the return shipping.</div></div></div>
    <div class="acc-item"><button class="acc-q" aria-expanded="false"><span class="ico"><i class="h"></i><i class="v"></i></span>Can your team help me identify a part?</button><div class="acc-a"><div class="inner">Absolutely. Our parts specialists can identify a component from a part number, a photo, or your vehicle details. Call or email us and we will confirm the correct part.</div></div></div>
    <div class="acc-item"><button class="acc-q" aria-expanded="false"><span class="ico"><i class="h"></i><i class="v"></i></span>How can I track my order?</button><div class="acc-a"><div class="inner">Every order includes tracking. Use the Track Order link in the header, or find live status and history under My Account once you are signed in.</div></div></div>
  </div>
</div></section>

<!-- ===== NEWSLETTER ===== -->
<section class="news"><div class="blueprint"></div><div class="grain"></div><div class="wrap">
  <div class="reveal">
    <span class="eyebrow on-navy">Stay Ahead of the Road</span>
    <h2>Get Parts Updates and Exclusive Offers</h2>
    <p>Receive product arrivals, vehicle maintenance tips, and special offers directly in your inbox.</p>
    <form onsubmit="return false">
      <div class="row"><input type="email" placeholder="Your email address" aria-label="Email address" required><button class="btn btn-red">Subscribe</button></div>
      <label class="chk"><input type="checkbox" checked>Send me new product updates and special offers</label>
      <div class="priv"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>We respect your privacy. Unsubscribe anytime.</div>
    </form>
  </div>
  <div class="art reveal" style="transition-delay:.08s"><img src="https://images.unsplash.com/photo-1552519507-da3b142c6e3d?q=80&w=900&auto=format&fit=crop" alt="Premium vehicle detail" loading="lazy"></div>
</div></section>

<!-- ===== FOOTER ===== -->
<footer>
  <div class="wrap">
    <div class="ftop">
      <div class="fbrand">
        <div class="logo"><svg class="mk" viewBox="0 0 40 40" fill="none"><rect width="40" height="40" rx="10" fill="#E01F26"/><path d="M11 26c1-6 4-9 7-9h4c3 0 6 3 7 9" stroke="#fff" stroke-width="2.3" stroke-linecap="round"/><path d="M20 8l3 5h-6l3-5Z" fill="#0B1E3B"/><circle cx="15" cy="27" r="3.4" fill="#fff"/><circle cx="25" cy="27" r="3.4" fill="#fff"/></svg><span><b>SUPREME AUTOS</b><span>QUALITY VEHICLE PARTS</span></span></div>
        <p>Quality replacement and performance parts matched to your exact vehicle. Trusted by DIYers and professional shops nationwide.</p>
        <div class="fcontact">
          <div class="ln"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M5 4h4l2 5-3 2a12 12 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg>1-800-555-0110</div>
          <div class="ln"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>parts@supremeautos.com</div>
          <div class="ln"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M12 21s-7-4.4-7-10a7 7 0 0 1 14 0c0 5.6-7 10-7 10Z"/><circle cx="12" cy="11" r="2.4"/></svg>1200 Motorway Drive, Detroit, MI</div>
        </div>
        <div class="fsocial">
          <a href="#" aria-label="Facebook"><svg width="17" height="17" fill="currentColor" viewBox="0 0 24 24"><path d="M13 22v-8h3l1-4h-4V8c0-1 .5-2 2-2h2V2h-3c-3 0-5 2-5 5v3H6v4h4v8z"/></svg></a>
          <a href="#" aria-label="Instagram"><svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1"/></svg></a>
          <a href="#" aria-label="YouTube"><svg width="17" height="17" fill="currentColor" viewBox="0 0 24 24"><path d="M22 8s-.2-1.5-.8-2.1c-.8-.8-1.7-.8-2.1-.9C16.3 4.8 12 4.8 12 4.8s-4.3 0-7.1.2c-.4.1-1.3.1-2.1.9C2.2 6.5 2 8 2 8s-.2 1.7-.2 3.5v1c0 1.8.2 3.5.2 3.5s.2 1.5.8 2.1c.8.8 1.9.8 2.3.9 1.7.2 6.9.2 6.9.2s4.3 0 7.1-.2c.4-.1 1.3-.1 2.1-.9.6-.6.8-2.1.8-2.1s.2-1.7.2-3.5v-1C22.2 9.7 22 8 22 8ZM10 14.6V9.4l4.5 2.6z"/></svg></a>
        </div>
      </div>
      <div class="fcol"><h5>Shop</h5><ul><li><a href="#">Parts Catalog</a></li><li><a href="#">Engine</a></li><li><a href="#">Brakes</a></li><li><a href="#">Suspension</a></li><li><a href="#">Electrical</a></li><li><a href="#">Wheels &amp; Tyres</a></li></ul></div>
      <div class="fcol"><h5>Customer Service</h5><ul><li><a href="#">Contact Us</a></li><li><a href="#">Track Order</a></li><li><a href="#">Shipping Info</a></li><li><a href="#">Returns</a></li><li><a href="#">Warranty</a></li><li><a href="#">FAQs</a></li></ul></div>
      <div class="fcol"><h5>Company</h5><ul><li><a href="#">About Us</a></li><li><a href="#">Our Brands</a></li><li><a href="#">Trade Accounts</a></li><li><a href="#">Careers</a></li><li><a href="#">Privacy Policy</a></li><li><a href="#">Terms</a></li></ul></div>
      <div class="fcol"><h5>Account</h5><ul><li><a href="#">My Account</a></li><li><a href="#">My Garage</a></li><li><a href="#">Saved Vehicles</a></li><li><a href="#">Wishlist</a></li><li><a href="#">Order History</a></li></ul></div>
    </div>
  </div>
  <div class="fdivider"></div>
  <div class="wrap"><div class="fbase">
    <span>© 2026 Supreme Autos. All rights reserved.</span>
    <span class="sp"></span>
    <div class="fpay"><span>VISA</span><span>MC</span><span>AMEX</span><span>PAY</span></div>
    <select class="fcurrency" aria-label="Currency"><option>USD $</option><option>EUR €</option><option>GBP £</option></select>
  </div></div>
</footer>

<button class="totop" id="totop" aria-label="Back to top"><svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 19V5M6 11l6-6 6 6"/></svg></button>

<!-- ===== MOBILE DRAWER ===== -->
<div class="drawer-ov" id="drawerOv"></div>
<aside class="drawer" id="drawer" aria-hidden="true">
  <div class="dh"><div class="logo"><svg class="mk" viewBox="0 0 40 40" fill="none" style="width:34px;height:34px"><rect width="40" height="40" rx="10" fill="#0B1E3B"/><path d="M11 26c1-6 4-9 7-9h4c3 0 6 3 7 9" stroke="#fff" stroke-width="2.3" stroke-linecap="round"/><path d="M20 8l3 5h-6l3-5Z" fill="#E01F26"/></svg><b style="font-size:16px;color:var(--navy)">SUPREME AUTOS</b></div><button class="iconbtn" id="drawerClose" aria-label="Close menu"><svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>
  <nav>
    <a href="#">Home <svg width="16" height="16" fill="none" stroke="var(--faint)" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></a>
    <a href="#catalog">Parts Catalog <svg width="16" height="16" fill="none" stroke="var(--faint)" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></a>
    <a href="#categories">Categories <svg width="16" height="16" fill="none" stroke="var(--faint)" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></a>
    <a href="#brands">Brands <svg width="16" height="16" fill="none" stroke="var(--faint)" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></a>
    <a href="#">About Us <svg width="16" height="16" fill="none" stroke="var(--faint)" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></a>
    <a href="#">Contact <svg width="16" height="16" fill="none" stroke="var(--faint)" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></a>
  </nav>
  <div class="df"><a class="btn btn-red btn-block" href="#catalog">Find Your Part</a><a class="btn btn-outline btn-block" href="#">Sign In</a></div>
</aside>

<script>window.SP={base:<?= json_encode($base, JSON_UNESCAPED_SLASHES) ?>};</script>
<script>
(function(){
  var rm=matchMedia('(prefers-reduced-motion: reduce)').matches;
  var SP_BASE=(window.SP&&window.SP.base)||'';
  function api(p){return fetch(SP_BASE+'/api'+p,{headers:{Accept:'application/json'}}).then(function(r){return r.ok?r.json():[]}).catch(function(){return[]})}
  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML}
  // sticky header shadow
  var hdr=document.getElementById('hdr');
  addEventListener('scroll',function(){hdr.classList.toggle('stuck',scrollY>4);document.getElementById('totop').classList.toggle('show',scrollY>600)},{passive:true});
  document.getElementById('totop').addEventListener('click',function(){scrollTo({top:0,behavior:rm?'auto':'smooth'})});
  // reveal
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:0,rootMargin:'0px 0px -8% 0px'});
  document.querySelectorAll('.reveal').forEach(function(el){io.observe(el)});
  requestAnimationFrame(function(){document.querySelectorAll('.reveal').forEach(function(el){if(el.getBoundingClientRect().top<innerHeight)el.classList.add('in')})});
  // mobile drawer
  var ov=document.getElementById('drawerOv'),dr=document.getElementById('drawer');
  function openD(){ov.classList.add('show');dr.classList.add('show');dr.setAttribute('aria-hidden','false');document.getElementById('burger').setAttribute('aria-expanded','true')}
  function closeD(){ov.classList.remove('show');dr.classList.remove('show');dr.setAttribute('aria-hidden','true');document.getElementById('burger').setAttribute('aria-expanded','false')}
  document.getElementById('burger').addEventListener('click',openD);
  document.getElementById('drawerClose').addEventListener('click',closeD);
  ov.addEventListener('click',closeD);
  dr.querySelectorAll('a').forEach(function(a){a.addEventListener('click',closeD)});
  // hero tabs
  document.querySelectorAll('.tab').forEach(function(t){t.addEventListener('click',function(){
    document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('on');x.setAttribute('aria-selected','false')});
    t.classList.add('on');t.setAttribute('aria-selected','true');
    var which=t.dataset.tab;
    document.getElementById('panel-veh').hidden=which!=='veh';
    document.getElementById('panel-vin').hidden=which!=='vin';
  })});
  // cascading vehicle selects -> real API (year -> make -> model -> engine/vehicle)
  var vy=document.getElementById('v-year'),vm=document.getElementById('v-make'),
      vmo=document.getElementById('v-model'),ve=document.getElementById('v-engine');
  function optFill(sel,items,ph,valfn,txtfn){
    if(!sel)return; sel.innerHTML='<option value="">'+ph+'</option>';
    items.forEach(function(it){var o=document.createElement('option');o.value=valfn(it);o.textContent=txtfn(it);sel.appendChild(o)});
  }
  if(vy){
    optFill(vm,[],'Select make'); optFill(vmo,[],'Select model'); optFill(ve,[],'Select engine');
    vm.disabled=vmo.disabled=ve.disabled=true;
    api('/years').then(function(ys){optFill(vy,ys,'Select year',function(y){return y},function(y){return y})});
    vy.addEventListener('change',function(){
      vmo.disabled=ve.disabled=true; optFill(vmo,[],'Select model'); optFill(ve,[],'Select engine');
      document.getElementById('veh-msg').classList.remove('err');
      if(!vy.value){vm.disabled=true;optFill(vm,[],'Select make');return}
      vm.disabled=false; api('/makes?year='+encodeURIComponent(vy.value)).then(function(ms){
        optFill(vm,ms,'Select make',function(m){return m.slug},function(m){return m.name})});
    });
    vm.addEventListener('change',function(){
      ve.disabled=true; optFill(ve,[],'Select engine');
      if(!vm.value){vmo.disabled=true;optFill(vmo,[],'Select model');return}
      vmo.disabled=false; api('/models?year='+encodeURIComponent(vy.value)+'&make='+encodeURIComponent(vm.value)).then(function(ms){
        optFill(vmo,ms,'Select model',function(m){return m.slug},function(m){return m.name})});
    });
    vmo.addEventListener('change',function(){
      if(!vmo.value){ve.disabled=true;optFill(ve,[],'Select engine');return}
      ve.disabled=false; api('/vehicles?year='+encodeURIComponent(vy.value)+'&make='+encodeURIComponent(vm.value)+'&model='+encodeURIComponent(vmo.value)).then(function(vs){
        optFill(ve,vs,'Select engine',function(v){return v.slug},function(v){return v.label})});
    });
  }
  document.getElementById('findParts').addEventListener('click',function(){
    var m=document.getElementById('veh-msg');
    if(!ve||!ve.value){m.classList.add('err');return}
    m.classList.remove('err'); this.innerHTML='Loading matching parts…';
    location.href=SP_BASE+'/vehicle/'+encodeURIComponent(ve.value);
  });
  // VIN validate
  var vin=document.getElementById('vin-input');
  document.getElementById('searchVin').addEventListener('click',function(){
    var err=document.getElementById('vin-msg'),ok=document.getElementById('vin-ok');
    err.classList.remove('err');ok.classList.remove('ok');
    if((vin.value||'').trim().length!==17){err.classList.add('err');vin.focus();return}
    ok.classList.add('ok');
    var b=this;b.innerHTML='Decoding VIN…';
    setTimeout(function(){location.hash='#catalog';b.innerHTML='Search VIN'},900);
  });
  vin.addEventListener('input',function(){this.value=this.value.toUpperCase().replace(/[^A-Z0-9]/g,'');document.getElementById('vin-msg').classList.remove('err')});
  // catalog: desktop 5-column browser -> real API drill-down
  var C_sel={year:{v:'',t:''},make:{v:'',t:''},model:{v:'',t:''},engine:{v:'',t:''},cat:{v:'',t:''}};
  var C_order=['make','year','model','engine','cat'];
  var C_label={year:'Year',make:'Make',model:'Model',engine:'Engine',cat:'Category'};
  function C_list(n){return document.querySelector('.cols .col[data-col="'+n+'"] .list')}
  function C_count(n,c){var el=document.querySelector('.cols .col[data-col="'+n+'"] .ch .n');if(el)el.textContent=(c==null?'—':c)}
  function C_crumb(){C_order.forEach(function(c){
    var s=document.querySelector('.crumbs .step[data-c="'+c+'"]');if(!s)return;
    s.innerHTML=C_sel[c].v?'<b style="color:var(--navy)">'+esc(C_sel[c].t)+'</b>':'<span class="ph">'+C_label[c]+'</span>';
  })}
  var C_chev='<span class="cv"><svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></span>';
  function C_flags(codes){
    if(!codes||!codes.length)return '';
    return '<span class="flags">'+codes.map(function(c){c=String(c).toLowerCase();
      return '<img class="flag" src="https://flagcdn.com/16x12/'+c+'.png" alt="'+esc(c.toUpperCase())+'" title="'+esc(c.toUpperCase())+'" loading="lazy">';}).join('')+'</span>';
  }
  function C_render(name,items,valfn,txtfn,countfn,flagsfn){
    var list=C_list(name);if(!list)return;
    if(!items.length){list.innerHTML='<div class="opt" style="color:var(--faint);cursor:default">None found</div>';C_count(name,0);return}
    C_count(name,items.length);list.innerHTML='';
    items.forEach(function(it){var v=valfn(it),t=txtfn(it),n=countfn?countfn(it):null,fl=flagsfn?flagsfn(it):null;
      var o=document.createElement('div');o.className='opt';o.dataset.v=v;o.dataset.t=t;
      o.innerHTML='<span class="opt-l">'+esc(t)+C_flags(fl)+'</span>'+(n!=null?'<span class="n">'+esc(n)+'</span>':C_chev);list.appendChild(o)});
  }
  function C_clearFrom(i){for(var j=i;j<C_order.length;j++){C_sel[C_order[j]]={v:'',t:''};var l=C_list(C_order[j]);if(l){l.innerHTML='';C_count(C_order[j],null)}}}
  function C_next(name){var mk=C_sel.make.v,y=C_sel.year.v,mo=C_sel.model.v,en=C_sel.engine.v;
    if(name==='make')api('/tree/years?make='+encodeURIComponent(mk)).then(function(d){C_render('year',d,function(x){return x},function(x){return x})});
    else if(name==='year')api('/models?year='+encodeURIComponent(y)+'&make='+encodeURIComponent(mk)).then(function(d){C_render('model',d,function(x){return x.slug},function(x){return x.name})});
    else if(name==='model')api('/vehicles?year='+encodeURIComponent(y)+'&make='+encodeURIComponent(mk)+'&model='+encodeURIComponent(mo)).then(function(d){C_render('engine',d,function(x){return x.slug},function(x){return x.label})});
    else if(name==='engine')api('/tree/groups?vehicle='+encodeURIComponent(en)).then(function(d){C_render('cat',d,function(x){return x.slug},function(x){return x.name},function(x){return x.n})});
  }
  document.querySelectorAll('.cols .col').forEach(function(col){
    var cname=col.dataset.col,list=col.querySelector('.list');
    if(list)list.addEventListener('click',function(ev){var opt=ev.target.closest('.opt');if(!opt||!opt.dataset.v)return;
      col.querySelectorAll('.opt').forEach(function(o){o.classList.remove('on')});opt.classList.add('on');
      C_sel[cname]={v:opt.dataset.v,t:opt.dataset.t};C_clearFrom(C_order.indexOf(cname)+1);C_crumb();
      if(cname!=='cat')C_next(cname);
    });
    var f=col.querySelector('.filt input');if(f)f.addEventListener('input',function(){var q=this.value.toLowerCase();col.querySelectorAll('.opt').forEach(function(o){o.style.display=o.textContent.toLowerCase().indexOf(q)>-1?'':'none'})});
  });
  if(document.querySelector('.cols')){
    ['year','model','engine','cat'].forEach(function(n){var l=C_list(n);if(l)l.innerHTML='';C_count(n,null)});
    var ml=C_list('make');if(ml)ml.innerHTML='';C_count('make',null);
    api('/tree/makes').then(function(ms){C_render('make',ms,function(x){return x.slug},function(x){return x.name},function(x){return x.n},function(x){return x.markets})});
  }
  document.getElementById('clearSel').addEventListener('click',function(){C_clearFrom(0);C_crumb()});
  var vmatch=document.getElementById('viewMatch');
  if(vmatch)vmatch.addEventListener('click',function(){if(C_sel.engine.v)location.href=SP_BASE+'/vehicle/'+encodeURIComponent(C_sel.engine.v)});
  // mobile catalog accordion (progressive)
  var mOrder=['year','make','model','engine','cat'];
  document.querySelectorAll('.mstep').forEach(function(st){
    st.querySelector('.mh').addEventListener('click',function(){
      if(st.getAttribute('aria-disabled')==='true')return;
      var wasOpen=st.classList.contains('open');
      document.querySelectorAll('.mstep').forEach(function(s){s.classList.remove('open')});
      if(!wasOpen)st.classList.add('open');
    });
    st.querySelectorAll('.opt').forEach(function(opt){opt.addEventListener('click',function(){
      st.querySelectorAll('.opt').forEach(function(o){o.classList.remove('on')});opt.classList.add('on');
      st.classList.add('done');st.querySelector('.val').textContent=opt.dataset.v;
      var i=mOrder.indexOf(st.dataset.step),nxt=document.querySelector('.mstep[data-step="'+mOrder[i+1]+'"]');
      st.classList.remove('open');
      if(nxt){nxt.setAttribute('aria-disabled','false');nxt.classList.add('open')}
    })});
  });
  // FAQ accordion
  document.querySelectorAll('.acc-item').forEach(function(it){
    var q=it.querySelector('.acc-q'),a=it.querySelector('.acc-a');
    if(it.classList.contains('open'))a.style.maxHeight=a.scrollHeight+'px';
    q.addEventListener('click',function(){
      var open=it.classList.contains('open');
      document.querySelectorAll('.acc-item').forEach(function(x){x.classList.remove('open');x.querySelector('.acc-q').setAttribute('aria-expanded','false');x.querySelector('.acc-a').style.maxHeight='0px'});
      if(!open){it.classList.add('open');q.setAttribute('aria-expanded','true');a.style.maxHeight=a.scrollHeight+'px'}
    });
  });
  // brand marquee (real SVG logos via Simple Icons, monochrome navy default)
  var brands=[['toyota','Toyota'],['honda','Honda'],['nissan','Nissan'],['ford','Ford'],['chevrolet','Chevrolet'],['bmw','BMW'],['mercedes','Mercedes-Benz'],['volkswagen','Volkswagen'],['audi','Audi'],['lexus','Lexus'],['hyundai','Hyundai'],['kia','Kia'],['subaru','Subaru'],['mazda','Mazda']];
  var track=document.getElementById('track');
  function logoEl(slug,name){var a=document.createElement('span');a.className='lg';a.innerHTML='<img src="https://cdn.simpleicons.org/'+slug+'/0B1E3B" data-color="https://cdn.simpleicons.org/'+slug+'" alt="'+name+'" loading="lazy" onerror="this.parentNode.innerHTML=\''+name+'\';this.parentNode.style.cssText=\'font-weight:700;color:#98a2b3;font-size:17px\'">';var img=a.querySelector('img');if(img)a.addEventListener('mouseenter',function(){img.src=img.dataset.color});return a}
  brands.concat(brands).forEach(function(b){track.appendChild(logoEl(b[0],b[1]))});
})();
</script>
</body>
</html>
