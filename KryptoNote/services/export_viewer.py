import base64
import html
import json


_EMBED_MARKER = "<!-- EMBEDDED_MEDIA -->"


def render_viewer_parts(manifest):
    """Return UTF-8 HTML parts around optional embedded media blocks."""
    payload = json.dumps(
        manifest, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    graph_data = base64.b64encode(payload).decode("ascii")
    title = html.escape(manifest.get("case", {}).get("name") or "KryptoNote Export")
    document = (
        _VIEWER_TEMPLATE.replace("__DOCUMENT_TITLE__", title)
        .replace("__GRAPH_DATA__", graph_data)
    )
    before, marker, after = document.partition(_EMBED_MARKER)
    if not marker:
        raise RuntimeError("Viewer template is missing its media marker")
    return before, after


def render_viewer(manifest):
    before, after = render_viewer_parts(manifest)
    return before + after


_VIEWER_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<title>__DOCUMENT_TITLE__ — KryptoNote Graph</title>
<style>
:root {
  --bg-canvas:#121212; --bg-panel:#1e1e1e; --bg-node:#26282b;
  --bg-input:#161616; --bg-control:#2d3034; --bg-hover:#35393e;
  --border:#3a3e43; --border-subtle:#303337; --text:#efefef;
  --text-dim:#bbbbbb; --text-muted:#92979f; --accent:#e6158b;
  --grid-main:#252525; --grid-sub:#1a1a1a; --connection-width:1.5px;
  --space-xs:4px; --space-sm:8px; --space-md:12px; --space-lg:16px;
  --toolbar-height:52px;
  font-family:"Segoe UI",system-ui,sans-serif;
}
* { box-sizing:border-box; }
html,body { width:100%; height:100%; margin:0; overflow:hidden; }
body { background:var(--bg-canvas); color:var(--text); font-size:14px; }
button,input { font:inherit; }
button {
  min-height:34px; border:1px solid var(--border); border-radius:4px;
  background:var(--bg-control); color:var(--text); padding:6px 10px;
  cursor:pointer; transition:background-color 120ms ease-out,border-color 120ms ease-out;
}
button:hover { background:var(--bg-hover); border-color:var(--text-muted); }
button:active { background:var(--bg-input); }
button:focus-visible,input:focus-visible,.graph-node:focus-visible {
  outline:2px solid var(--accent); outline-offset:2px;
}
.toolbar {
  position:fixed; inset:0 0 auto 0; z-index:30; min-height:var(--toolbar-height);
  display:flex; align-items:center; gap:var(--space-sm); padding:8px 12px;
  border-bottom:1px solid var(--border-subtle); background:var(--bg-panel);
}
.identity { min-width:0; margin-right:auto; display:flex; align-items:baseline; gap:8px; }
.identity strong { font-size:15px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.identity span { color:var(--text-muted); font-size:12px; white-space:nowrap; }
.search-wrap { position:relative; width:min(340px,34vw); }
.search-wrap input {
  width:100%; height:34px; border:1px solid var(--border); border-radius:4px;
  background:var(--bg-input); color:var(--text); padding:6px 10px;
}
.search-wrap input::placeholder { color:var(--text-muted); opacity:1; }
.search-results {
  position:fixed; z-index:40; display:none; max-height:min(420px,60vh); overflow:auto;
  border:1px solid var(--border); border-radius:6px; background:var(--bg-panel);
}
.search-results.open { display:block; }
.search-result {
  width:100%; min-height:42px; display:block; border:0; border-radius:0;
  border-bottom:1px solid var(--border-subtle); text-align:left; background:transparent;
}
.search-result:last-child { border-bottom:0; }
.search-result small { display:block; color:var(--text-muted); margin-top:2px; }
.zoom-readout { min-width:54px; color:var(--text-dim); text-align:center; font-variant-numeric:tabular-nums; }
.viewport { position:absolute; inset:var(--toolbar-height) 0 0 0; overflow:hidden; touch-action:none; cursor:grab; }
.viewport.panning { cursor:grabbing; }
.canvas {
  position:absolute; left:0; top:0; transform-origin:0 0;
  background-color:var(--bg-canvas);
  background-image:
    linear-gradient(var(--grid-main) 1px,transparent 1px),
    linear-gradient(90deg,var(--grid-main) 1px,transparent 1px),
    linear-gradient(var(--grid-sub) 1px,transparent 1px),
    linear-gradient(90deg,var(--grid-sub) 1px,transparent 1px);
  background-size:500px 500px,500px 500px,100px 100px,100px 100px;
}
.connections { position:absolute; inset:0; z-index:1; overflow:visible; pointer-events:none; }
.connection { fill:none; stroke:var(--border); stroke-width:var(--connection-width); stroke-linecap:round; }
.graph-node {
  z-index:2;
  position:absolute; overflow:hidden; border:1.1px solid var(--border); border-radius:4px;
  background:var(--bg-node); color:var(--text); cursor:pointer; text-align:left;
  transition:border-color 120ms ease-out,background-color 120ms ease-out;
}
.graph-node:hover { border-color:var(--accent); }
.frame-node {
  z-index:0; overflow:visible; border-radius:8px;
  background:color-mix(in srgb,var(--bg-panel) 21%,transparent);
}
.frame-node .node-inner {
  position:absolute; top:-15px; left:50%; width:max-content;
  min-width:96px; max-width:calc(100% - 24px); height:30px;
  transform:translateX(-50%); padding:0 12px;
  flex-direction:row; align-items:center; justify-content:center; gap:7px;
  border:1px solid var(--border); border-radius:15px; background:var(--bg-node);
}
.frame-node .node-title {
  min-width:0; color:var(--text); white-space:nowrap;
  text-overflow:ellipsis; display:block; text-align:center;
}
.frame-lock-indicator {
  position:relative; flex:0 0 11px; width:11px; height:9px;
  margin-top:3px; border:1.5px solid currentColor; border-radius:2px;
  color:var(--text-muted);
}
.frame-lock-indicator::before {
  content:""; position:absolute; left:1.5px; top:-7px; width:6px; height:7px;
  border:1.5px solid currentColor; border-bottom:0; border-radius:5px 5px 0 0;
}
.frame-lock-indicator.locked { color:var(--text); }
.frame-lock-indicator.unlocked::before {
  left:5px; transform:rotate(28deg); transform-origin:1px 7px;
}
.node-inner { position:relative; height:100%; display:flex; flex-direction:column; padding:8px 12px; }
.media-node .node-inner { padding:5px 10px; }
.node-title {
  flex:0 0 auto; color:var(--accent); font-family:"Segoe UI Semibold","Segoe UI",sans-serif;
  font-weight:600; line-height:1.25; overflow:hidden; display:-webkit-box;
  -webkit-line-clamp:3; -webkit-box-orient:vertical;
}
.media-node .node-title { color:var(--text); white-space:nowrap; text-overflow:ellipsis; display:block; }
.node-body { flex:1 1 auto; min-height:0; margin-top:6px; overflow:hidden; line-height:1.32; color:var(--text); overflow-wrap:anywhere; }
.node-body:first-child { margin-top:0; }
.node-body p { margin:0 0 5px; }
.node-body p:last-child { margin-bottom:0; }
.node-body h1,.node-body h2,.node-body h3 { margin:4px 0 5px; line-height:1.2; color:var(--text); }
.node-body h1 { font-size:1.65em; }.node-body h2 { font-size:1.4em; }.node-body h3 { font-size:1.18em; }
.node-body ul,.node-body ol { margin:3px 0 5px; padding-left:20px; }
.node-body blockquote { margin:4px 0; padding-left:8px; border-left:2px solid var(--border); color:var(--text-dim); }
.node-body pre { margin:3px 0 5px; white-space:pre-wrap; line-height:1.25; font-family:Consolas,monospace; color:var(--text-dim); }
.node-body code { font-family:Consolas,monospace; color:var(--text-dim); }
.media-frame {
  position:relative; flex:1 1 auto; min-height:40px; margin-top:5px; display:flex; align-items:center;
  justify-content:center; overflow:hidden; border:1px solid var(--border);
  border-radius:3px; background:var(--bg-panel);
}
.media-frame img { width:100%; height:100%; padding:2px; display:block; object-fit:contain; }
.media-frame span { color:var(--text-muted); }
.media-frame .tag-chip,.media-frame .tag-chip-label { color:var(--text); }
.node-footer { flex:0 0 auto; min-height:18px; padding-top:5px; color:var(--accent); font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.tag-strip { height:20px; min-width:0; display:flex; align-items:center; gap:4px; overflow:hidden; background:transparent; pointer-events:none; }
.tag-strip.text-tags { position:absolute; z-index:2; left:10px; right:10px; bottom:10px; }
.tag-strip.media-tags { position:absolute; z-index:2; left:6px; right:6px; bottom:6px; margin:0; }
.tag-strip.frame-tags { position:absolute; z-index:2; left:28px; right:28px; bottom:-9px; }
.tag-chip { flex:0 1 auto; max-width:112px; height:20px; display:inline-flex; align-items:center; gap:5px; padding:0 6px; border:1px solid currentColor; border-radius:7px; color:var(--text); font-family:"Segoe UI Semibold","Segoe UI",sans-serif; font-size:9.33px; white-space:nowrap; overflow:hidden; }
.tag-chip-label { overflow:hidden; text-overflow:ellipsis; }
.tag-dot { flex:0 0 7px; width:7px; height:7px; border-radius:50%; background:currentColor; }
.tag-more { flex:0 0 auto; height:20px; display:inline-flex; align-items:center; justify-content:center; padding:0 6px; border:1px solid var(--border); border-radius:7px; background:var(--bg-node); color:var(--text-dim); font-family:"Segoe UI Semibold","Segoe UI",sans-serif; font-size:9.33px; }
.empty-state {
  position:fixed; inset:var(--toolbar-height) 0 0; display:none; place-items:center;
  color:var(--text-dim); text-align:center; padding:24px;
}
.empty-state.visible { display:grid; }
dialog {
  width:min(920px,calc(100vw - 32px)); max-height:calc(100vh - 48px); padding:0;
  border:1px solid var(--border); border-radius:8px; background:var(--bg-panel); color:var(--text);
}
dialog::backdrop { background:rgba(0,0,0,.72); }
.detail-head {
  position:sticky; top:0; z-index:2; display:flex; align-items:flex-start; gap:12px;
  padding:14px 16px; border-bottom:1px solid var(--border-subtle); background:var(--bg-panel);
}
.detail-title { min-width:0; margin:0 auto 0 0; font-size:18px; line-height:1.25; text-wrap:balance; }
.detail-content { padding:18px 20px 24px; }
.detail-content img,.detail-content video,.detail-content audio { display:block; max-width:100%; max-height:65vh; margin:0 auto; background:var(--bg-input); }
.detail-content audio { width:min(680px,100%); }
.waveform { display:flex; align-items:center; gap:2px; width:min(680px,100%); height:64px; margin:14px auto 0; padding:8px; border:1px solid var(--border); border-radius:4px; background:var(--bg-input); }
.waveform-bar { flex:1 1 0; min-width:1px; border-radius:2px; background:var(--accent); opacity:.8; }
.detail-copy { max-width:72ch; line-height:1.55; overflow-wrap:anywhere; }
.detail-copy h1,.detail-copy h2,.detail-copy h3 { color:var(--accent); line-height:1.25; text-wrap:balance; }
.detail-copy pre { overflow:auto; padding:12px; border:1px solid var(--border); background:var(--bg-input); }
.detail-copy code { font-family:Consolas,monospace; background:var(--bg-input); padding:1px 3px; border-radius:2px; }
.meta { display:flex; flex-wrap:wrap; gap:6px 12px; margin-top:16px; color:var(--text-muted); font-size:12px; }
.tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:14px; }
.tag { border:1px solid currentColor; border-radius:8px; padding:3px 7px; color:var(--text); font-size:12px; }
.links { margin-top:18px; padding-top:14px; border-top:1px solid var(--border-subtle); }
.links button { margin:4px 4px 0 0; }
.media-fallback { margin-top:12px; color:var(--text-dim); }
.media-fallback a { color:var(--accent); }
@media (max-width:760px) {
  :root { --toolbar-height:96px; }
  .toolbar { flex-wrap:wrap; align-content:center; }
  .identity span,.zoom-readout { display:none; }
  .search-wrap { order:3; width:100%; }
  .toolbar button { min-width:40px; }
  .detail-content { padding:14px; }
}
@media (pointer:coarse) { button { min-height:44px; } }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { scroll-behavior:auto!important; transition-duration:0.01ms!important; } }
</style>
</head>
<body>
<header class="toolbar" aria-label="Graph controls">
  <div class="identity"><strong id="case-name"></strong><span id="graph-summary"></span></div>
  <div class="search-wrap"><input id="search" type="search" placeholder="Search nodes and tags" aria-label="Search nodes and tags" autocomplete="off"><div id="search-results" class="search-results" role="listbox"></div></div>
  <button id="zoom-out" type="button" aria-label="Zoom out">−</button>
  <span id="zoom-readout" class="zoom-readout" aria-live="polite">100%</span>
  <button id="zoom-in" type="button" aria-label="Zoom in">+</button>
  <button id="fit" type="button">Fit graph</button>
</header>
<main id="viewport" class="viewport" aria-label="Read-only graph canvas">
  <div id="canvas" class="canvas">
    <svg id="connections" class="connections" aria-hidden="true"></svg>
  </div>
</main>
<section id="empty-state" class="empty-state"><div><strong>No nodes in this export</strong><br><span>The project was exported successfully, but the graph is empty.</span></div></section>
<dialog id="detail">
  <header class="detail-head"><h1 id="detail-title" class="detail-title"></h1><button id="detail-close" type="button" aria-label="Close details">Close</button></header>
  <div id="detail-content" class="detail-content"></div>
</dialog>
<script id="graph-data" type="application/octet-stream">__GRAPH_DATA__</script>
<!-- EMBEDDED_MEDIA -->
<script>
(async () => {
  "use strict";
  const byId = id => document.getElementById(id);
  const decodeBase64 = value => {
    const clean = value.replace(/\s+/g, "");
    const parts = [];
    const slice = 1024 * 1024;
    for (let offset = 0; offset < clean.length; offset += slice) {
      const binary = atob(clean.slice(offset, offset + slice));
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      parts.push(bytes);
    }
    return parts;
  };
  const graphBytes = decodeBase64(byId("graph-data").textContent);
  const graph = JSON.parse(await new Blob(graphBytes).text());
  const nodes = graph.nodes || [];
  const connections = graph.connections || [];
  const nodeMap = new Map(nodes.map(node => [node.id, node]));
  const urlCache = new Map();
  const palette = (graph.appearance && graph.appearance.palette) || {};
  const root = document.documentElement.style;
  const paletteMap = {
    bg_canvas:"--bg-canvas",bg_panel:"--bg-panel",bg_node:"--bg-node",bg_input:"--bg-input",
    bg_control:"--bg-control",bg_control_hover:"--bg-hover",border_default:"--border",
    border_subtle:"--border-subtle",text_main:"--text",text_dim:"--text-dim",
    text_muted:"--text-muted",accent_main:"--accent",grid_main:"--grid-main",grid_sub:"--grid-sub"
  };
  Object.entries(paletteMap).forEach(([key,css]) => { if (palette[key]) root.setProperty(css,palette[key]); });
  const width = graph.appearance && graph.appearance.connection_width;
  if (width) root.setProperty("--connection-width", `${Number(width)}px`);

  const viewport = byId("viewport");
  const canvas = byId("canvas");
  const svg = byId("connections");
  const dialog = byId("detail");
  const detailTitle = byId("detail-title");
  const detailContent = byId("detail-content");
  const search = byId("search");
  const results = byId("search-results");
  const readout = byId("zoom-readout");
  let scale = 1;
  let tx = 0;
  let ty = 0;
  let panning = false;
  let pointerStart = null;
  let graphBounds = {minX:0,minY:0,width:1,height:1,offsetX:0,offsetY:0};

  const clamp = (value,min,max) => Math.max(min,Math.min(max,value));
  const safeText = value => String(value == null ? "" : value);
  const fileSource = (node,thumbnail=false) => {
    const embeddedId = `${thumbnail ? "embedded-thumb" : "embedded-media"}-${node.id}`;
    const embedded = byId(embeddedId);
    if (embedded) {
      if (!urlCache.has(embeddedId)) {
        const mime = embedded.dataset.mime || "application/octet-stream";
        urlCache.set(embeddedId,URL.createObjectURL(new Blob(decodeBase64(embedded.textContent),{type:mime})));
      }
      return urlCache.get(embeddedId);
    }
    if (!node.media) return "";
    return thumbnail ? (node.media.thumbnail || node.media.path || "") : (node.media.path || "");
  };
  const escapeHtml = value => safeText(value).replace(/[&<>"']/g,char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
  const inlineMarkdown = value => {
    let line = escapeHtml(value);
    line = line.replace(/`([^`]+)`/g,"<code>$1</code>");
    line = line.replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>");
    line = line.replace(/(^|\s)\*([^*]+)\*/g,"$1<em>$2</em>");
    line = line.replace(/\[([^\]]+)\]\(([^)]+)\)/g,(_all,label,url) => {
      const allowed = /^(https?:|mailto:|#)/i.test(url.trim());
      return allowed ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
    });
    return line;
  };
  const renderMarkdown = value => {
    const lines = safeText(value).replace(/\r\n?/g,"\n").split("\n");
    const out = [];
    let inCode = false;
    let listType = "";
    let paragraph = [];
    const flushParagraph = () => {
      if (!paragraph.length) return;
      out.push(`<p>${paragraph.map(inlineMarkdown).join("<br>")}</p>`);
      paragraph=[];
    };
    const closeList = () => {
      if (!listType) return;
      out.push(`</${listType}>`);
      listType="";
    };
    for (const raw of lines) {
      if (/^\s*```/.test(raw)) {
        flushParagraph(); closeList();
        out.push(inCode ? "</code></pre>" : "<pre><code>");
        inCode = !inCode;
        continue;
      }
      if (inCode) { out.push(`${escapeHtml(raw)}\n`); continue; }
      if (!raw.trim()) { flushParagraph(); closeList(); continue; }
      const heading = raw.match(/^\s*(#{1,3})\s+(.+)/);
      if (heading) {
        flushParagraph(); closeList();
        const level=heading[1].length;
        out.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
        continue;
      }
      const unordered=raw.match(/^\s*[-*+]\s+(.+)/);
      const ordered=raw.match(/^\s*\d+[.)]\s+(.+)/);
      if (unordered || ordered) {
        flushParagraph();
        const nextType=ordered ? "ol" : "ul";
        if (listType!==nextType) { closeList(); listType=nextType; out.push(`<${listType}>`); }
        out.push(`<li>${inlineMarkdown((ordered||unordered)[1])}</li>`);
        continue;
      }
      closeList();
      if (/^\s*>\s?/.test(raw)) {
        flushParagraph();
        out.push(`<blockquote>${inlineMarkdown(raw.replace(/^\s*>\s?/,""))}</blockquote>`);
      } else {
        paragraph.push(raw.trim());
      }
    }
    flushParagraph(); closeList();
    if (inCode) out.push("</code></pre>");
    return out.join("");
  };
  const formatBytes = size => {
    const value=Number(size||0); if (!value) return "0 B";
    const units=["B","KiB","MiB","GiB","TiB"]; const index=Math.min(units.length-1,Math.floor(Math.log(value)/Math.log(1024)));
    return `${(value/Math.pow(1024,index)).toFixed(index ? 1 : 0)} ${units[index]}`;
  };
  const duration = seconds => {
    const value=Math.max(0,Math.round(Number(seconds||0))); const h=Math.floor(value/3600); const m=Math.floor((value%3600)/60); const s=value%60;
    return h ? `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}` : `${m}:${String(s).padStart(2,"0")}`;
  };
  const formatTimestamp = value => {
    const text=safeText(value).trim(); if (!text) return "";
    const match=text.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
    return match ? `${match[1]} ${match[2]}` : text;
  };
  const formatAppBytes = size => {
    let value=Number(size||0); if (!value) return "";
    const units=["B","KB","MB","GB"];
    for (const unit of units) {
      if (value<1024 || unit===units[units.length-1]) return unit==="B" ? `${Math.round(value)} ${unit}` : `${value.toFixed(1)} ${unit}`;
      value/=1024;
    }
    return "";
  };
  const rgbColor = value => {
    const color=safeText(value).trim(); const short=color.match(/^#([0-9a-f]{3})$/i); const full=color.match(/^#([0-9a-f]{6})$/i);
    if (short) return short[1].split("").map(char=>parseInt(char+char,16));
    if (full) return [parseInt(full[1].slice(0,2),16),parseInt(full[1].slice(2,4),16),parseInt(full[1].slice(4,6),16)];
    return null;
  };
  const tagBackground = value => {
    const base=rgbColor(palette.bg_node||"#26282b"),tint=rgbColor(value); if (!base || !tint) return "var(--bg-node)";
    return `rgb(${base.map((channel,index)=>Math.round(channel*.8+tint[index]*.2)).join(",")})`;
  };
  const tagMetrics=document.createElement("canvas").getContext("2d"); tagMetrics.font='600 9.33px "Segoe UI"';
  const tagWidth = (tag,compact=false) => Math.min(112,Math.max(compact ? 30 : 36,Math.ceil(tagMetrics.measureText(safeText(tag.name)).width)+(compact ? 12 : 30)));
  const moreWidth = count => Math.max(26,Math.ceil(tagMetrics.measureText(`+${count}`).width)+12);
  const renderTagStrip = (tags,placement="text",nodeWidth=200) => {
    if (!tags || !tags.length) return null;
    const strip=document.createElement("div"); strip.className=`tag-strip ${placement}-tags`;
    const compact=placement==="frame";
    const available=Math.max(0,Number(nodeWidth)-(placement==="media" ? 32 : compact ? 56 : 20)); let used=0,displayCount=0;
    for (let index=0;index<tags.length;index+=1) {
      const next=tagWidth(tags[index],compact)+(displayCount ? 4 : 0),remaining=tags.length-index-1;
      const total=used+next+(remaining ? 4+moreWidth(remaining) : 0); if (total>available) break;
      used+=next; displayCount+=1;
    }
    if (!displayCount && tags.length===1) displayCount=1;
    else if (!displayCount && tags.length>1 && available>=4+moreWidth(tags.length-1)+18) displayCount=1;
    tags.slice(0,displayCount).forEach(tag => {
      const chip=document.createElement("span"); chip.className="tag-chip"; chip.style.width=`${Math.min(tagWidth(tag,compact),available)}px`; chip.style.borderColor=tag.color; chip.style.background=tagBackground(tag.color);
      const label=document.createElement("span"); label.className="tag-chip-label"; label.textContent=tag.name; chip.title=tag.name;
      if (!compact) { const dot=document.createElement("span"); dot.className="tag-dot"; dot.style.color=tag.color; chip.appendChild(dot); }
      chip.appendChild(label); strip.appendChild(chip);
    });
    const remaining=tags.length-displayCount; if (remaining>0) { const more=document.createElement("span"); more.className="tag-more"; more.textContent=`+${remaining}`; strip.appendChild(more); }
    return strip;
  };
  const linkedNodes = id => connections.filter(c => c.start_id===id || c.end_id===id).map(c => nodeMap.get(c.start_id===id ? c.end_id : c.start_id)).filter(Boolean);

  function calculateBounds() {
    if (!nodes.length) return;
    const minX=Math.min(...nodes.map(n => Number(n.position.x)));
    const minY=Math.min(...nodes.map(n => Number(n.position.y)));
    const maxX=Math.max(...nodes.map(n => Number(n.position.x)+Number(n.size.width)));
    const maxY=Math.max(...nodes.map(n => Number(n.position.y)+Number(n.size.height)));
    const margin=180;
    graphBounds={minX,minY,width:Math.max(1,maxX-minX+margin*2),height:Math.max(1,maxY-minY+margin*2),offsetX:margin-minX,offsetY:margin-minY};
    canvas.style.width=`${graphBounds.width}px`; canvas.style.height=`${graphBounds.height}px`;
    svg.setAttribute("width",graphBounds.width); svg.setAttribute("height",graphBounds.height); svg.setAttribute("viewBox",`0 0 ${graphBounds.width} ${graphBounds.height}`);
  }
  const edgePoint = (a,b,anchorMode) => {
    const cx=Number(a.position.x)+Number(a.size.width)/2+graphBounds.offsetX;
    const cy=Number(a.position.y)+Number(a.size.height)/2+graphBounds.offsetY;
    const tx=Number(b.position.x)+Number(b.size.width)/2+graphBounds.offsetX;
    const ty=Number(b.position.y)+Number(b.size.height)/2+graphBounds.offsetY;
    const dx=tx-cx,dy=ty-cy,hw=Number(a.size.width)/2,hh=Number(a.size.height)/2;
    if (Math.abs(dx)<.01 && Math.abs(dy)<.01) return [cx,cy];
    const inset=a.type==="frame" ? 0 : 8,anchorWidth=Math.max(1,hw-inset),anchorHeight=Math.max(1,hh-inset);
    if (anchorMode==="side_centers") {
      if (Math.abs(dx)/anchorWidth>=Math.abs(dy)/anchorHeight) return [cx+(dx>=0 ? anchorWidth : -anchorWidth),cy];
      return [cx,cy+(dy>=0 ? anchorHeight : -anchorHeight)];
    }
    const sx=Math.abs(dx)>0.01 ? anchorWidth/Math.abs(dx) : Infinity;
    const sy=Math.abs(dy)>0.01 ? anchorHeight/Math.abs(dy) : Infinity;
    const factor=Math.min(sx,sy); return [cx+dx*factor,cy+dy*factor];
  };
  const pointDistance=(a,b)=>Math.hypot(b[0]-a[0],b[1]-a[1]);
  const compactPoints=points=>points.filter((point,index)=>!index || pointDistance(points[index-1],point)>.001);
  const pointToward=(origin,target,distance)=>{
    const length=pointDistance(origin,target); if (length<=.001) return origin;
    const amount=distance/length; return [origin[0]+(target[0]-origin[0])*amount,origin[1]+(target[1]-origin[1])*amount];
  };
  const stableNormal=(dx,dy,length)=>{
    let nx=-dy/length,ny=dx/length;
    if (ny<-.001 || (Math.abs(ny)<=.001 && nx<0)) { nx=-nx; ny=-ny; }
    return [nx,ny];
  };
  function routePoints(style,start,end) {
    const dx=end[0]-start[0],dy=end[1]-start[1],horizontal=Math.abs(dx)>=Math.abs(dy);
    if (style==="orthogonal") {
      if (horizontal) { const middle=(start[0]+end[0])/2; return compactPoints([start,[middle,start[1]],[middle,end[1]],end]); }
      const middle=(start[1]+end[1])/2; return compactPoints([start,[start[0],middle],[end[0],middle],end]);
    }
    if (horizontal) {
      const direction=dx>=0 ? 1 : -1,lead=Math.min(Math.abs(dx)/3,48);
      return compactPoints([start,[start[0]+direction*lead,start[1]],[end[0]-direction*lead,end[1]],end]);
    }
    const direction=dy>=0 ? 1 : -1,lead=Math.min(Math.abs(dy)/3,48);
    return compactPoints([start,[start[0],start[1]+direction*lead],[end[0],end[1]-direction*lead],end]);
  }
  function roundedPolylinePath(points,radius) {
    if (points.length<2) return "";
    let path=`M ${points[0][0]} ${points[0][1]}`;
    for (let index=1;index<points.length-1;index+=1) {
      const previous=points[index-1],corner=points[index],following=points[index+1];
      const local=Math.min(radius,pointDistance(previous,corner)/2,pointDistance(corner,following)/2);
      if (local<=.001) { path+=` L ${corner[0]} ${corner[1]}`; continue; }
      const entry=pointToward(corner,previous,local),exit=pointToward(corner,following,local);
      path+=` L ${entry[0]} ${entry[1]} Q ${corner[0]} ${corner[1]} ${exit[0]} ${exit[1]}`;
    }
    const end=points[points.length-1]; return path+` L ${end[0]} ${end[1]}`;
  }
  function connectionPath(style,start,end,curveFormula,cornerStyle) {
    if (style==="straight") return `M ${start[0]} ${start[1]} L ${end[0]} ${end[1]}`;
    const cornerRadius=cornerStyle==="sharp" ? 0 : (cornerStyle==="tight" ? 8 : 24);
    if (style==="orthogonal" || style==="angled") return roundedPolylinePath(routePoints(style,start,end),cornerRadius);
    const dx=end[0]-start[0],dy=end[1]-start[1],length=pointDistance(start,end);
    if (curveFormula==="arc" && length>.001) {
      const normal=stableNormal(dx,dy,length),bow=Math.min(80,length*.22);
      const control=[(start[0]+end[0])/2+normal[0]*bow,(start[1]+end[1])/2+normal[1]*bow];
      return `M ${start[0]} ${start[1]} Q ${control[0]} ${control[1]} ${end[0]} ${end[1]}`;
    }
    if (curveFormula==="s_curve" && length>.001) {
      const normal=stableNormal(dx,dy,length),bow=Math.min(64,length*.18);
      const c1=[start[0]+dx/3+normal[0]*bow,start[1]+dy/3+normal[1]*bow];
      const c2=[start[0]+dx*2/3-normal[0]*bow,start[1]+dy*2/3-normal[1]*bow];
      return `M ${start[0]} ${start[1]} C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${end[0]} ${end[1]}`;
    }
    if (curveFormula==="adaptive" && Math.abs(dy)>Math.abs(dx)) {
      return `M ${start[0]} ${start[1]} C ${start[0]} ${start[1]+dy*.4}, ${end[0]} ${end[1]-dy*.4}, ${end[0]} ${end[1]}`;
    }
    return `M ${start[0]} ${start[1]} C ${start[0]+dx*.4} ${start[1]}, ${end[0]-dx*.4} ${end[1]}, ${end[0]} ${end[1]}`;
  }
  function renderConnections() {
    const appearance=graph.appearance || {};
    const style=appearance.connection_style || "curved";
    const curveFormula=appearance.connection_curve_formula || "horizontal";
    const cornerStyle=appearance.connection_corner_style || "smooth";
    const anchorMode=appearance.connection_anchor_mode || "perimeter";
    const pattern=appearance.connection_pattern || "solid";
    connections.forEach(connection => {
      const start=nodeMap.get(connection.start_id),end=nodeMap.get(connection.end_id); if (!start || !end) return;
      const [x1,y1]=edgePoint(start,end,anchorMode),[x2,y2]=edgePoint(end,start,anchorMode);
      const path=document.createElementNS("http://www.w3.org/2000/svg","path"); path.classList.add("connection");
      path.setAttribute("d",connectionPath(style,[x1,y1],[x2,y2],curveFormula,cornerStyle));
      if (pattern==="dashed") path.style.strokeDasharray="8 5";
      else if (pattern==="dotted") path.style.strokeDasharray="1 5";
      svg.appendChild(path);
    });
  }
  function renderNodes() {
    nodes.forEach(node => {
      const element=document.createElement("article");
      const typeClass=node.type==="frame" ? "frame-node" : (node.type==="text" ? "text-node" : "media-node");
      element.className=`graph-node ${typeClass}`;
      element.tabIndex=0; element.dataset.id=String(node.id); element.setAttribute("role","button"); element.setAttribute("aria-label",`${node.type} node: ${node.title || `Node ${node.id}`}`);
      element.style.left=`${Number(node.position.x)+graphBounds.offsetX}px`; element.style.top=`${Number(node.position.y)+graphBounds.offsetY}px`;
      element.style.width=`${Math.max(80,Number(node.size.width))}px`; element.style.height=`${Math.max(60,Number(node.size.height))}px`;
      if (node.type==="frame") {
        const frameAppearance=node.frame_appearance||{};
        const frameColor=frameAppearance.color||"var(--bg-panel)";
        const frameOpacity=Math.max(0,Math.min(1,Number(frameAppearance.opacity ?? .21)));
        element.style.background=`color-mix(in srgb,${frameColor} ${Math.round(frameOpacity*100)}%,transparent)`;
      }
      const inner=document.createElement("div"); inner.className="node-inner";
      const displayTitle=node.type==="frame" ? (safeText(node.title).trim() || "Untitled Frame") : safeText(node.title).trim();
      if (node.type==="frame") {
        const lock=document.createElement("span");
        lock.className=`frame-lock-indicator ${node.locked ? "locked" : "unlocked"}`;
        lock.setAttribute("aria-label",node.locked ? "Locked" : "Unlocked");
        inner.appendChild(lock);
        const title=document.createElement("div"); title.className="node-title"; title.textContent=displayTitle;
        title.style.fontSize=`${Math.max(9,Number(node.font && node.font.title_size || 14))}pt`; inner.appendChild(title);
      } else if (displayTitle) {
        const title=document.createElement("div"); title.className="node-title"; title.textContent=displayTitle;
        title.style.fontSize=`${Math.max(9,Number(node.font && node.font.title_size || 14))}pt`; inner.appendChild(title);
      }
      if (node.type==="frame") {
        // A frame is a spatial backdrop. Its title is the complete content.
      } else if (node.type==="text") {
        const body=document.createElement("div"); body.className="node-body"; body.innerHTML=renderMarkdown(node.content || "");
        body.style.fontSize=`${Math.max(8,Number(node.font && node.font.text_size || 10))}pt`; inner.appendChild(body);
        const tags=renderTagStrip(node.tags,"text",node.size.width); if (tags) inner.appendChild(tags);
      } else {
        const frame=document.createElement("div"); frame.className="media-frame"; const source=fileSource(node,true);
        if (source) { const image=document.createElement("img"); image.loading="lazy"; image.alt=""; image.src=source; frame.appendChild(image); }
        else { const label=document.createElement("span"); label.textContent="No thumbnail"; frame.appendChild(label); }
        const tags=renderTagStrip(node.tags,"media",node.size.width); if (tags) frame.appendChild(tags);
        inner.appendChild(frame); const footer=document.createElement("div"); footer.className="node-footer";
        const parts=[formatTimestamp(node.created_at)];
        if ((node.type==="video" || node.type==="audio") && node.media.duration) parts.push(duration(node.media.duration));
        if (node.media.size) parts.push(formatAppBytes(node.media.size));
        if (node.media.width && node.media.height) parts.push(`${node.media.width}x${node.media.height}`);
        footer.textContent=parts.filter(Boolean).join(" | ") || `[${safeText(node.type).toUpperCase()}]`; inner.appendChild(footer);
      }
      element.appendChild(inner);
      if (node.type==="frame") { const tags=renderTagStrip(node.tags,"frame",node.size.width); if (tags) element.appendChild(tags); }
      element.addEventListener("click",() => openNode(node)); element.addEventListener("keydown",event => { if (event.key==="Enter" || event.key===" ") { event.preventDefault(); openNode(node); } }); canvas.appendChild(element);
    });
  }
  function openNode(node) {
    detailTitle.textContent=node.title || `Node ${node.id}`; detailContent.replaceChildren();
    if (node.type==="text") { const copy=document.createElement("div"); copy.className="detail-copy"; copy.innerHTML=renderMarkdown(node.content||""); detailContent.appendChild(copy); }
    else if (node.type==="frame") { const copy=document.createElement("p"); copy.textContent=node.locked ? "Locked frame · contained nodes move with it." : "Unlocked frame · moves independently."; detailContent.appendChild(copy); }
    else if (node.type==="image") { const image=document.createElement("img"); image.alt=node.title||"Exported image"; image.src=fileSource(node,false)||fileSource(node,true); detailContent.appendChild(image); }
    else if (node.type==="audio") {
      const audio=document.createElement("audio"); audio.controls=true; audio.setAttribute("controls",""); audio.preload="metadata"; audio.src=fileSource(node,false); detailContent.appendChild(audio);
      const waveform=document.createElement("div"); waveform.className="waveform"; waveform.setAttribute("role","img"); waveform.setAttribute("aria-label","Audio waveform");
      (node.media.waveform||[]).forEach(value => { const bar=document.createElement("span"); bar.className="waveform-bar"; bar.style.height=`${Math.max(4,Math.min(100,Number(value||0)*100))}%`; waveform.appendChild(bar); });
      if (waveform.childElementCount) detailContent.appendChild(waveform);
      const fallback=document.createElement("p"); fallback.className="media-fallback"; fallback.textContent="If this format is not supported by your browser, "; const link=document.createElement("a"); link.href=fileSource(node,false); link.textContent="open the original audio"; link.target="_blank"; fallback.appendChild(link); fallback.append(" in a desktop player."); detailContent.appendChild(fallback);
    }
    else { const video=document.createElement("video"); video.controls=true; video.preload="metadata"; video.poster=fileSource(node,true); video.src=fileSource(node,false); detailContent.appendChild(video); const fallback=document.createElement("p"); fallback.className="media-fallback"; fallback.textContent="If this format is not supported by your browser, "; const link=document.createElement("a"); link.href=fileSource(node,false); link.textContent="open the original video"; link.target="_blank"; fallback.appendChild(link); fallback.append(" in a desktop player."); detailContent.appendChild(fallback); }
    if ((node.type==="image" || node.type==="video" || node.type==="audio") && node.content) { const copy=document.createElement("div"); copy.className="detail-copy"; copy.innerHTML=renderMarkdown(node.content); detailContent.appendChild(copy); }
    const meta=document.createElement("div"); meta.className="meta"; const values=[`Type: ${node.type}`,`Node ID: ${node.id}`];
    if (node.type==="frame") values.push(`Lock: ${node.locked ? "locked" : "unlocked"}`);
    if (node.media) { values.push(`Size: ${formatBytes(node.media.size)}`); if (node.media.width || node.media.height) values.push(`Dimensions: ${node.media.width||0}×${node.media.height||0}`); if (node.media.duration) values.push(`Duration: ${duration(node.media.duration)}`); if (node.media.original_filename) values.push(`Original: ${node.media.original_filename}`); }
    values.forEach(value => { const span=document.createElement("span"); span.textContent=value; meta.appendChild(span); }); detailContent.appendChild(meta);
    if (node.tags && node.tags.length) { const tags=document.createElement("div"); tags.className="tags"; node.tags.forEach(tag => { const chip=document.createElement("span"); chip.className="tag"; chip.style.borderColor=tag.color; chip.textContent=tag.name; tags.appendChild(chip); }); detailContent.appendChild(tags); }
    const linked=linkedNodes(node.id); if (linked.length) { const links=document.createElement("nav"); links.className="links"; const label=document.createElement("strong"); label.textContent="Connected nodes"; links.appendChild(label); links.appendChild(document.createElement("br")); linked.forEach(target => { const button=document.createElement("button"); button.type="button"; button.textContent=target.title||`Node ${target.id}`; button.addEventListener("click",() => { dialog.close(); focusNode(target.id); }); links.appendChild(button); }); detailContent.appendChild(links); }
    dialog.showModal();
  }
  function applyTransform() { canvas.style.transform=`translate(${tx}px,${ty}px) scale(${scale})`; readout.textContent=`${Math.round(scale*100)}%`; }
  function fitGraph(allowUpscale=false) { if (!nodes.length) return; const pad=36,maxScale=allowUpscale ? 1.25 : 1; scale=clamp(Math.min((viewport.clientWidth-pad*2)/graphBounds.width,(viewport.clientHeight-pad*2)/graphBounds.height),.04,maxScale); tx=(viewport.clientWidth-graphBounds.width*scale)/2; ty=(viewport.clientHeight-graphBounds.height*scale)/2; applyTransform(); }
  function focusNode(id) { const node=nodeMap.get(Number(id)); if (!node) return; scale=clamp(Math.max(scale,.65),.04,2.5); const x=(Number(node.position.x)+graphBounds.offsetX+Number(node.size.width)/2)*scale; const y=(Number(node.position.y)+graphBounds.offsetY+Number(node.size.height)/2)*scale; tx=viewport.clientWidth/2-x; ty=viewport.clientHeight/2-y; applyTransform(); const element=canvas.querySelector(`[data-id="${node.id}"]`); if (element) { element.focus({preventScroll:true}); element.animate([{borderColor:"var(--accent)"},{borderColor:"var(--border)"}],{duration:700,easing:"ease-out"}); } }
  function zoomAt(next,cx=viewport.clientWidth/2,cy=viewport.clientHeight/2) { const old=scale; scale=clamp(next,.04,2.5); tx=cx-(cx-tx)*(scale/old); ty=cy-(cy-ty)*(scale/old); applyTransform(); }
  function positionResults() { const rect=search.getBoundingClientRect(); results.style.left=`${rect.left}px`; results.style.top=`${rect.bottom+4}px`; results.style.width=`${rect.width}px`; }
  function runSearch() { const query=search.value.trim().toLocaleLowerCase(); results.replaceChildren(); if (!query) { results.classList.remove("open"); return; } const matches=nodes.filter(node => `${node.title||""}\n${node.content||""}\n${(node.tags||[]).map(t=>t.name).join(" ")}`.toLocaleLowerCase().includes(query)).slice(0,30); matches.forEach(node => { const button=document.createElement("button"); button.type="button"; button.className="search-result"; const title=document.createElement("span"); title.textContent=node.title||`Node ${node.id}`; const meta=document.createElement("small"); meta.textContent=`${node.type} · Node ${node.id}`; button.append(title,meta); button.addEventListener("click",() => { results.classList.remove("open"); focusNode(node.id); }); results.appendChild(button); }); if (!matches.length) { const empty=document.createElement("div"); empty.className="search-result"; empty.textContent="No matching nodes"; results.appendChild(empty); } positionResults(); results.classList.add("open"); }

  byId("case-name").textContent=(graph.case&&graph.case.name)||"KryptoNote Export";
  byId("graph-summary").textContent=`${nodes.length} nodes · ${connections.length} connections`;
  if (!nodes.length) byId("empty-state").classList.add("visible");
  calculateBounds(); renderConnections(); renderNodes(); fitGraph(false);
  byId("fit").addEventListener("click",() => fitGraph(true)); byId("zoom-in").addEventListener("click",() => zoomAt(scale*1.2)); byId("zoom-out").addEventListener("click",() => zoomAt(scale/1.2));
  byId("detail-close").addEventListener("click",() => dialog.close()); dialog.addEventListener("click",event => { if (event.target===dialog) dialog.close(); });
  search.addEventListener("input",runSearch); search.addEventListener("keydown",event => { if (event.key==="Enter") { const first=results.querySelector("button"); if (first) first.click(); } });
  window.addEventListener("resize",() => { positionResults(); fitGraph(false); });
  viewport.addEventListener("wheel",event => { event.preventDefault(); const rect=viewport.getBoundingClientRect(); zoomAt(scale*Math.exp(-event.deltaY*.0015),event.clientX-rect.left,event.clientY-rect.top); },{passive:false});
  viewport.addEventListener("pointerdown",event => { if (event.button!==0 || event.target.closest(".graph-node")) return; panning=true; pointerStart={x:event.clientX,y:event.clientY,tx,ty}; viewport.classList.add("panning"); viewport.setPointerCapture(event.pointerId); });
  viewport.addEventListener("pointermove",event => { if (!panning) return; tx=pointerStart.tx+event.clientX-pointerStart.x; ty=pointerStart.ty+event.clientY-pointerStart.y; applyTransform(); });
  viewport.addEventListener("pointerup",event => { panning=false; viewport.classList.remove("panning"); if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId); });
  document.addEventListener("keydown",event => { if ((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="f") { event.preventDefault(); search.focus(); search.select(); } else if (event.key.toLowerCase()==="f" && document.activeElement!==search) fitGraph(true); else if ((event.key==="+"||event.key==="=") && document.activeElement!==search) zoomAt(scale*1.2); else if (event.key==="-" && document.activeElement!==search) zoomAt(scale/1.2); });
})();
</script>
</body>
</html>
'''
