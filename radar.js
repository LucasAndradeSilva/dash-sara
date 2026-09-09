"use strict";
const RAW = JSON.parse(document.getElementById('dashboard-data').textContent);
const CULTOS = RAW.cultos;
const CULT_MAP = Object.fromEntries(CULTOS.map(c => [c.id, c]));
const personKey = r => r.telefone_norm || r.nome.toLowerCase();
const historyByPerson = new Map();
for(const r of RAW.registros){
  const key=personKey(r);
  if(!historyByPerson.has(key)) historyByPerson.set(key,[]);
  historyByPerson.get(key).push(r);
}
for(const rows of historyByPerson.values()) rows.sort((a,b)=>a.data_iso.localeCompare(b.data_iso));
const firstVisit = new Map([...historyByPerson].map(([key,rows])=>[key,rows[0].data_iso]));


const SERIES_COLORS = ['#137b62','#337eaa','#b58a43','#79a99a','#72839f','#a0aeb9'];
const COLORS = {
  text:'#526777', grid:'#e9eef2',
  accent:'#137b62', success:'#137b62', warning:'#b58a43', info:'#337eaa', danger:'#ba4242',
  series: SERIES_COLORS,
  muted:'#b9c7d0'
};

if(window.Chart){
  Chart.defaults.color = COLORS.text;
  Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
  Chart.defaults.font.size = 13;
  Chart.defaults.borderColor = COLORS.grid;
}

/* ---------------- ICONS (inline SVG, no external deps) ---------------- */
const SVG = {
  up:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg>',
  down:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M18 13l-6 6-6-6"/></svg>',
  chevronLeft:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  chevronRight:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>'
};

let charts = {};
let mobileVisibleCount = 12;
const MOBILE_PAGE_STEP = 12;

let state = {
  dateFrom: RAW.meta.periodo_inicio ? isoFromBr(RAW.meta.periodo_inicio) : '',
  dateTo: RAW.meta.periodo_fim ? isoFromBr(RAW.meta.periodo_fim) : '',
  preset: 'all',
  cultos: new Set(CULTOS.map(c => c.id)),
  search: '',
  retorno: 'all',
  page: 1,
  pageSize: 25,
  activeTab: 'visao'
};

function isoFromBr(d){ if(!d) return ''; const [dd,mm,yy]=d.split('/'); return `${yy}-${mm}-${dd}`; }
function brFromIso(iso){ if(!iso) return ''; const [y,m,d]=iso.split('-'); return `${d}/${m}/${y}`; }
function fmtMonth(m){ const [y,mo]=m.split('-'); const n=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']; return n[+mo-1]+'/'+y.slice(2); }
function fmtNum(n){ return (n||0).toLocaleString('pt-BR'); }
function escapeHtml(s){ return String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function mondayOf(iso){ const d = new Date(iso+'T00:00:00'); const day = (d.getDay()+6)%7; d.setDate(d.getDate()-day); return d.toISOString().slice(0,10); }
function splitTrendPct(arr){
  if(!arr.length) return 0;
  const half = Math.floor(arr.length/2);
  const a = arr.slice(0,half).reduce((x,y)=>x+y,0);
  const b = arr.slice(half).reduce((x,y)=>x+y,0);
  return a ? Math.round((b-a)/a*1000)/10 : (b>0 ? 100 : 0);
}

function isMobile(){ return window.matchMedia('(max-width:1023.98px)').matches; }

function inRange(iso){
  if(state.dateFrom && iso < state.dateFrom) return false;
  if(state.dateTo && iso > state.dateTo) return false;
  return true;
}

function filterRegistros(){
  return RAW.registros.filter(r => state.cultos.has(r.culto_id) && inRange(r.data_iso));
}
function filterParticipacao(){
  return (RAW.participacao || []).filter(r => state.cultos.has(r.culto_id) && inRange(r.date_iso));
}

/* ---------------- STATS ---------------- */
function computeStats(regs, participacao){
  const byCultoDate = {}, byPhone = {}, byMonth = {}, novosMonth = {}, byWeek = {};
  const firstSeen = {};
  const sorted = [...regs].sort((a,b)=>a.data_iso.localeCompare(b.data_iso));

  for(const r of sorted){
    const cultoDateKey = `${r.data_iso}__${r.culto_id}`;
    if(!byCultoDate[cultoDateKey]) byCultoDate[cultoDateKey] = {date:r.data, date_iso:r.data_iso, culto_id:r.culto_id, culto:r.culto, weekday:r.weekday, count:0};
    byCultoDate[cultoDateKey].count++;

    const key = r.telefone_norm || r.nome.toLowerCase();
    if(!byPhone[key]) byPhone[key] = {key,nome:r.nome, telefone:r.telefone, email:r.email, visitas:0, cultos:new Set(), historico:[], genero:null, origem:null, observacao:null};
    byPhone[key].visitas++;
    byPhone[key].cultos.add(r.culto);
    byPhone[key].historico.push({data:r.data, data_iso:r.data_iso, culto:r.culto, hora:r.hora});
    byPhone[key].nome = r.nome || byPhone[key].nome;
    if(r.genero) byPhone[key].genero = r.genero;
    if(r.origem) byPhone[key].origem = r.origem;
    if(r.contato && r.contato !== '-') byPhone[key].observacao = r.contato;

    const mk = r.data_iso.slice(0,7);
    byMonth[mk] = (byMonth[mk]||0) + 1;
    if(!firstSeen[key]){ firstSeen[key]=r.data_iso; if(firstVisit.get(key)===r.data_iso) novosMonth[mk]=(novosMonth[mk]||0)+1; }

    const wk = mondayOf(r.data_iso);
    byWeek[wk] = (byWeek[wk]||0) + 1;
  }

  const cultoOrder = Object.fromEntries(CULTOS.map((c, i) => [c.id, i]));
  const ranking = Object.values(byCultoDate).sort((a,b)=>a.date_iso.localeCompare(b.date_iso) || (cultoOrder[a.culto_id] ?? 999) - (cultoOrder[b.culto_id] ?? 999));

  const counts = ranking.map(r=>r.count);
  const evolucao = ranking.map((r,i)=>{
    const chunk = counts.slice(Math.max(0,i-2), i+1);
    return {...r, ma3: Math.round(chunk.reduce((a,b)=>a+b,0)/chunk.length*100)/100};
  });

  const distCulto = CULTOS.map(c=>({...c, count: regs.filter(r=>r.culto_id===c.id).length}));
  const distWd = ['Terça','Quinta','Sábado','Domingo'].map(day=>({day, count: regs.filter(r=>r.weekday===day).length}));

  const months = [...new Set(Object.keys(byMonth))].sort();
  const crescimento = months.map((m,i)=>{
    const count = byMonth[m];
    const prev = i? byMonth[months[i-1]] : null;
    const pct = prev? Math.round((count-prev)/prev*1000)/10 : null;
    return {month:m, count, pct};
  });
  const novosPorMes = months.map(m=>({month:m, count: novosMonth[m]||0}));

  const pessoas = Object.values(byPhone).map(p=>{
    const hist = p.historico;
    const ultimaIso = hist[hist.length-1].data_iso;
    return {
      key:p.key, nome: p.nome||'Sem nome', telefone:p.telefone, email:p.email||'',
      visitas:p.visitas, cultos:[...p.cultos], historico:hist,
      genero:p.genero, origem:p.origem, observacao:p.observacao,
      primeira:hist[0].data, ultima:hist[hist.length-1].data, ultima_iso:ultimaIso
    };
  }).sort((a,b)=>b.ultima_iso.localeCompare(a.ultima_iso) || b.visitas-a.visitas || a.nome.localeCompare(b.nome));

  const genero = {masculino:0, feminino:0, nao_informado:0};
  const origemMap = {};
  for(const r of sorted){
    if(r.genero==='masculino') genero.masculino++;
    else if(r.genero==='feminino') genero.feminino++;
    else genero.nao_informado++;
    if(r.origem) origemMap[r.origem] = (origemMap[r.origem]||0)+1;
  }
  const origem = Object.entries(origemMap).sort((a,b)=>b[1]-a[1]).map(([nome,count])=>({nome, count}));

  const retornaram = pessoas.filter(p=>p.visitas>1).length;
  const freq = {};
  pessoas.forEach(p=>{ freq[p.visitas]=(freq[p.visitas]||0)+1; });

  const maior = ranking.length? ranking.reduce((a,b)=>b.count>a.count?b:a) : null;
  const menor = ranking.length? ranking.reduce((a,b)=>b.count<a.count?b:a) : null;
  const media = ranking.length? Math.round(regs.length/ranking.length*100)/100 : 0;

  const tendencia = splitTrendPct(counts);

  const weekKeys = Object.keys(byWeek).sort();
  const weeklyCounts = weekKeys.map(k=>byWeek[k]);
  const mediaSemanal = weekKeys.length? Math.round(regs.length/weekKeys.length*10)/10 : 0;
  const weeklyTrend = splitTrendPct(weeklyCounts);

  const novosEsteMes = novosPorMes.length? novosPorMes[novosPorMes.length-1].count : 0;
  let novosTrendPct = null;
  if(novosPorMes.length>=2){
    const prev = novosPorMes[novosPorMes.length-2].count;
    novosTrendPct = prev? Math.round((novosEsteMes-prev)/prev*1000)/10 : (novosEsteMes>0?100:0);
  }

  const selectedKeys = new Set(regs.map(personKey));
  const newPeople = [...selectedKeys].filter(k=>inRange(firstVisit.get(k))).length;
  const returningPeople = [...selectedKeys].filter(k=>new Set(historyByPerson.get(k).filter(r=>!state.dateTo||r.data_iso<=state.dateTo).map(r=>r.data_iso+'__'+r.culto_id)).size>1).length;
  const monthlyPeople = months.map(month=>{
    const keys=new Set(regs.filter(r=>r.data_iso.startsWith(month)).map(personKey));
    const n=[...keys].filter(k=>inRange(firstVisit.get(k)) && firstVisit.get(k).startsWith(month)).length;
    return {month,new:n,returning:keys.size-n};
  });
  for(const p of pessoas){
    const key=p.key;
    p.isNew=inRange(firstVisit.get(key));
    p.hasReturned=new Set((historyByPerson.get(key)||[]).filter(r=>!state.dateTo||r.data_iso<=state.dateTo).map(r=>r.data_iso+'__'+r.culto_id)).size>1;
  }
  const taxaRetorno = pessoas.length? Math.round(returningPeople/pessoas.length*1000)/10 : 0;

  const part = participacao || [];
  const totalMembros = part.reduce((a,r)=>a+(r.member_count||0),0);
  const totalCriancas = part.reduce((a,r)=>a+(r.children_count||0),0);

  return {
    newPeople, returningPeople, monthlyPeople, total: regs.length, n_cultos: ranking.length, unicos: pessoas.length, retornaram:returningPeople, media,
    maior, menor, ranking: [...ranking].sort((a,b)=>b.count-a.count),
    evolucao, distCulto, distWd, crescimento,
    novos_por_mes: novosPorMes,
    pessoas, freq, tendencia, genero, origem,
    participacao: part, totalMembros, totalCriancas,
    mediaSemanal, weeklyTrend, novosEsteMes, novosTrendPct, taxaRetorno
  };
}

/* ---------------- KPI RENDER ---------------- */
function badgeHtml(pct, flatLabel){
  if(flatLabel) return `<span class="kpi-badge flat">${flatLabel}</span>`;
  if(pct === null || pct === undefined) return '';
  const up = pct >= 0;
  return `<span class="kpi-badge ${up?'up':'down'}">${up?SVG.up:SVG.down} ${up?'+':''}${pct}%</span>`;
}

/* Analyses derived from the existing visitor and attendance records. */
function renderKpis(s){
  const items=[
    ['Registros de visitantes',fmtNum(s.total),'Visitas registradas no período'],
    ['Pessoas únicas',fmtNum(s.unicos),'Identificadas por telefone ou nome'],
    ['Novos no período',fmtNum(s.newPeople),'Primeira visita em todo o histórico'],
    ['Pessoas que retornaram',fmtNum(s.returningPeople),'Mais de uma data/culto até o fim do período']
  ];
  document.getElementById('kpiGrid').innerHTML=items.map(([label,value,note])=>`<div class="kpi-card"><div class="kpi-top"><span class="kpi-label">${label}</span><span class="kpi-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="8" r="3"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/></svg></span></div><div class="kpi-value">${value}</div><div class="kpi-note">${note}</div></div>`).join('');
}
function renderLead(s){
  const selected=CULTOS.filter(c=>state.cultos.has(c.id));
  document.getElementById('filterSummary').textContent=`${brFromIso(state.dateFrom)||'Início'} — ${brFromIso(state.dateTo)||'Fim'} · ${selected.length===CULTOS.length?'Todos os cultos':selected.map(c=>c.nome).join(' · ')||'Nenhum culto'}`;
  document.getElementById('visaoLead').textContent=`${fmtNum(s.total)} registros e ${fmtNum(s.unicos)} pessoas no período selecionado.`;
  document.getElementById('dataStamp').textContent=`Dados até ${RAW.meta.periodo_fim}`;
  document.getElementById('emptyNotice').hidden=Boolean(s.total || s.participacao.length);
}
function renderInsights(s){
  const insights=[];
  if(s.maior) insights.push(['Maior movimento',`<strong>${fmtNum(s.maior.count)} registros</strong> em ${s.maior.date}, no ${escapeHtml(s.maior.culto)}.`]);
  if(s.unicos) insights.push(['Acolhimento',`<strong>${fmtNum(s.newPeople)} pessoas</strong> tiveram a primeira visita registrada no período. Veja os nomes na aba Visitantes, usando o filtro “Novos no período”.`]);
  if(s.participacao.length){
    insights.push(['Cobertura de presença',`Há <strong>${s.participacao.length} contagens</strong> de membros e crianças no filtro. Cultos sem contagem ficam sem valor; eles não entram na média de presença.`]);
  }else insights.push(['Contagem de presença','Não há contagens de membros e crianças neste período. Os indicadores de visitantes continuam disponíveis.']);
  document.getElementById('insightsRow').innerHTML=insights.map(([tag,txt])=>`<article class="insight-card"><div class="insight-tag">${tag}</div><p class="insight-txt">${txt}</p></article>`).join('');
}
function renderPastoralOverview(s){
  const known=s.origem.reduce((sum,o)=>sum+o.count,0);
  document.getElementById('originSummary').innerHTML=s.origem.slice(0,4).map(o=>`<div class="origin-row"><div class="origin-label"><span>${escapeHtml(o.nome)}</span><strong>${fmtNum(o.count)}</strong></div><div class="origin-track"><span style="width:${known?o.count/known*100:0}%"></span></div></div>`).join('')+`<p class="origin-coverage">${fmtNum(known)} de ${fmtNum(s.total)} registros com origem informada.${s.total?' '+Math.round(known/s.total*100)+'% de preenchimento.':''}</p>`;
  const n=s.participacao.length;
  document.getElementById('participationSummary').innerHTML=`<div><h2>Presença nos cultos</h2><p>Somatório das contagens disponíveis.<br>Não são pessoas únicas.</p></div><div class="participation-metric"><strong>${n?fmtNum(s.totalMembros):'—'}</strong><span>Membros</span></div><div class="participation-metric"><strong>${n?fmtNum(s.totalCriancas):'—'}</strong><span>Crianças</span></div><div class="participation-metric"><strong>${n?fmtNum(Math.round((s.totalMembros+s.totalCriancas)/n)):'—'}</strong><span>Média por contagem</span></div>`;
  const services=new Map(s.evolucao.map(r=>[r.date_iso+'__'+r.culto_id,{...r,member_count:null,children_count:null}]));
  for(const p of s.participacao){
    const key=p.date_iso+'__'+p.culto_id;
    services.set(key,{...(services.get(key)||{date:p.date,date_iso:p.date_iso,culto:p.culto,count:null}),member_count:p.member_count,children_count:p.children_count});
  }
  const order=Object.fromEntries(CULTOS.map((c,i)=>[c.nome,i]));
  document.getElementById('recentServices').innerHTML=[...services.values()].sort((a,b)=>b.date_iso.localeCompare(a.date_iso)||(order[b.culto]??0)-(order[a.culto]??0)).slice(0,6).map(r=>`<tr><td>${r.date}</td><td>${escapeHtml(r.culto)}</td><td>${r.count===null?'—':fmtNum(r.count)}</td><td>${r.member_count===null?'—':fmtNum(r.member_count)}</td><td>${r.children_count===null?'—':fmtNum(r.children_count)}</td></tr>`).join('')||'<tr><td colspan="5">Nenhum registro neste filtro.</td></tr>';
}
function renderPastoralCharts(s){
  destroyChart('cultoAverage'); destroyChart('newReturning');
  const avg=s.distCulto.filter(c=>c.count).map(c=>({...c,average:c.count/s.evolucao.filter(e=>e.culto_id===c.id).length}));
  charts.cultoAverage=new Chart(document.getElementById('chartCultoAverage'),{type:'bar',data:{labels:avg.map(c=>c.nome),datasets:[{label:'Registros por culto',data:avg.map(c=>Math.round(c.average*10)/10),backgroundColor:COLORS.series,borderRadius:5}]},options:chartOpts({indexAxis:'y',plugins:{legend:{display:false},tooltip:{enabled:true}}})});
  charts.newReturning=new Chart(document.getElementById('chartNewReturning'),{type:'bar',data:{labels:s.monthlyPeople.map(m=>fmtMonth(m.month)),datasets:[{label:'Primeira visita',data:s.monthlyPeople.map(m=>m.new),backgroundColor:COLORS.accent,borderRadius:4},{label:'Já visitaram antes',data:s.monthlyPeople.map(m=>m.returning),backgroundColor:COLORS.info,borderRadius:4}]},options:chartOpts({plugins:{legend:{position:'bottom'},tooltip:{enabled:true}},scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,beginAtZero:true,ticks:{precision:0}}}})});
}

/* ---------------- CHARTS ---------------- */
function destroyChart(id){ if(charts[id]){ charts[id].destroy(); delete charts[id]; } }

function getOrCreateTooltip(chart){
  let el = chart.canvas.parentNode.querySelector('.chart-tooltip');
  if(!el){ el = document.createElement('div'); el.className='chart-tooltip'; chart.canvas.parentNode.appendChild(el); }
  return el;
}
function externalTooltip(context){
  const {chart, tooltip} = context;
  const el = getOrCreateTooltip(chart);
  if(tooltip.opacity === 0){ el.style.opacity = 0; return; }
  if(tooltip.body){
    const titleLines = tooltip.title || [];
    const bodyLines = tooltip.body.map(b=>b.lines).flat();
    let inner = titleLines.map(t=>`<div class="tt-title">${escapeHtml(t)}</div>`).join('');
    inner += bodyLines.map(l=>`<div class="tt-line">${escapeHtml(l)}</div>`).join('');
    el.innerHTML = inner;
  }
  const {offsetLeft:posX, offsetTop:posY} = chart.canvas;
  el.style.opacity = 1;
  el.style.left = (posX + tooltip.caretX) + 'px';
  el.style.top = (posY + tooltip.caretY) + 'px';
}

function chartOpts(extra={}){
  return {
    responsive:true, maintainAspectRatio:false,
    plugins:{legend:{labels:{color:COLORS.text, boxWidth:12, usePointStyle:true}}, tooltip:{enabled:false, external:externalTooltip}},
    scales:{
      x:{grid:{color:COLORS.grid}, ticks:{color:COLORS.text}},
      y:{grid:{color:COLORS.grid}, ticks:{color:COLORS.text}, beginAtZero:true}
    },
    ...extra
  };
}

function renderCharts(s){
  destroyChart('trend');
  charts.trend = new Chart(document.getElementById('chartTrend'),{
    data:{
      labels:s.evolucao.map(d=>d.date.slice(0,5)+' · '+d.culto),
      datasets:[
        {type:'bar', label:'Registros de visitantes', data:s.evolucao.map(d=>d.count), backgroundColor:'#c2dfd5', borderRadius:4, maxBarThickness:14, order:2},
        {type:'line', label:'Média móvel (3)', data:s.evolucao.map(d=>d.ma3), borderColor:COLORS.accent, pointRadius:0, borderWidth:2, tension:.35, order:1}
      ]
    },
    options:chartOpts({interaction:{mode:'index',intersect:false}, scales:{x:{ticks:{maxRotation:0,minRotation:0,maxTicksLimit:isMobile()?4:7,callback:function(value){return this.getLabelForValue(value).slice(0,5)}}}}})
  });

  destroyChart('mes');
  charts.mes = new Chart(document.getElementById('chartMes'),{
    type:'bar',
    data:{labels:s.crescimento.map(d=>fmtMonth(d.month)), datasets:[{data:s.crescimento.map(d=>d.count), backgroundColor:COLORS.accent, borderRadius:6, maxBarThickness:44}]},
    options:chartOpts({plugins:{legend:{display:false}, tooltip:{enabled:false, external:externalTooltip}}})
  });

  destroyChart('novos');
  charts.novos = new Chart(document.getElementById('chartNovos'),{
    type:'bar',
    data:{labels:s.novos_por_mes.map(d=>fmtMonth(d.month)), datasets:[{data:s.novos_por_mes.map(d=>d.count), backgroundColor:COLORS.info, borderRadius:6, maxBarThickness:44}]},
    options:chartOpts({plugins:{legend:{display:false}}})
  });

  destroyChart('cultos');
  charts.cultos = new Chart(document.getElementById('chartCultos'),{
    type:'doughnut',
    data:{labels:s.distCulto.map(d=>d.nome), datasets:[{data:s.distCulto.map(d=>d.count), backgroundColor:COLORS.series, borderWidth:0}]},
    options:{responsive:true, maintainAspectRatio:false, cutout:'62%', plugins:{legend:{position:'bottom', labels:{color:COLORS.text, boxWidth:10, padding:10}}, tooltip:{enabled:false, external:externalTooltip}}}
  });

  destroyChart('weekday');
  charts.weekday = new Chart(document.getElementById('chartWeekday'),{
    type:'bar',
    data:{labels:s.distWd.map(d=>d.day), datasets:[{data:s.distWd.map(d=>d.count), backgroundColor:COLORS.success, borderRadius:6, maxBarThickness:44}]},
    options:chartOpts({plugins:{legend:{display:false}}})
  });

  destroyChart('freq');
  charts.freq = new Chart(document.getElementById('chartFreq'),{
    type:'bar',
    data:{labels:Object.keys(s.freq).map(v=>v==='1'?'1 visita':v+' visitas'), datasets:[{data:Object.values(s.freq), backgroundColor:COLORS.warning, borderRadius:6}]},
    options:chartOpts({indexAxis:'y', plugins:{legend:{display:false}}})
  });

  destroyChart('genero');
  const g = s.genero;
  const hasGenero = g.masculino + g.feminino > 0;
  document.getElementById('generoPlaceholder').style.display = hasGenero? 'none':'block';
  charts.genero = new Chart(document.getElementById('chartGenero'),{
    type:'doughnut',
    data:{labels:['Masculino','Feminino','Não informado'], datasets:[{data:[g.masculino,g.feminino,g.nao_informado], backgroundColor:[COLORS.info,COLORS.accent,COLORS.muted], borderWidth:0}]},
    options:{responsive:true, maintainAspectRatio:false, cutout:'55%', plugins:{legend:{position:'bottom', labels:{color:COLORS.text}}, tooltip:{enabled:false, external:externalTooltip}}}
  });

  destroyChart('origem');
  const origens = s.origem || [];
  const hasOrigem = origens.length > 0;
  document.getElementById('origemPlaceholder').style.display = hasOrigem? 'none':'block';
  charts.origem = new Chart(document.getElementById('chartOrigem'),{
    type:'bar',
    data:{labels: hasOrigem? origens.map(o=>o.nome):['—'], datasets:[{data: hasOrigem? origens.map(o=>o.count):[0], backgroundColor:COLORS.accent, borderRadius:6}]},
    options:chartOpts({indexAxis:'y', plugins:{legend:{display:false}}})
  });

  destroyChart('participacao');
  const part = s.participacao || [];
  const hasPart = part.length > 0;
  const partCanvas = document.getElementById('chartParticipacao');
  document.getElementById('participacaoPlaceholder').style.display = hasPart? 'none':'block';
  partCanvas.parentElement.style.display = hasPart? 'block':'none';
  charts.participacao = new Chart(partCanvas,{
    type:'bar',
    data:{
      labels: hasPart? part.map(p=>`${p.date.slice(0,5)} · ${p.culto}`):['—'],
      datasets:[
        {label:'Membros', data: hasPart? part.map(p=>p.member_count):[0], backgroundColor:COLORS.info, borderRadius:6, maxBarThickness:36},
        {label:'Crianças', data: hasPart? part.map(p=>p.children_count):[0], backgroundColor:COLORS.warning, borderRadius:6, maxBarThickness:36}
      ]
    },
    options:chartOpts({
      plugins:{legend:{display:true, position:'top', labels:{color:COLORS.text, boxWidth:12, usePointStyle:true}}, tooltip:{enabled:false, external:externalTooltip}},
      scales:{x:{grid:{color:COLORS.grid}, ticks:{color:COLORS.text, maxRotation:45, minRotation:0}}, y:{grid:{color:COLORS.grid}, ticks:{color:COLORS.text}, beginAtZero:true}}
    })
  });
}

/* ---------------- VISITANTES TAB ---------------- */
function fmtGenero(g){ return g==='masculino'?'Masculino':g==='feminino'?'Feminino':'—'; }

function filteredPessoas(s){
  let list = s.pessoas;
  const q = state.search.toLowerCase().trim();
  if(q) list = list.filter(p =>
    p.nome.toLowerCase().includes(q) || p.telefone.includes(q) ||
    (p.email&&p.email.toLowerCase().includes(q)) || p.cultos.some(c=>c.toLowerCase().includes(q)) ||
    (p.observacao&&p.observacao.toLowerCase().includes(q))
  );
  if(state.retorno==='novos') list = list.filter(p=>p.isNew);
  if(state.retorno==='retorno') list = list.filter(p=>p.hasReturned);
  return list;
}

let currentPessoasList = [];

function renderVisitorsSummary(s, list){
  document.getElementById('visitorsSummary').innerHTML =
    `<strong>${fmtNum(list.length)}</strong> pessoas encontradas de <strong>${fmtNum(s.unicos)}</strong> únicas · <strong>${fmtNum(s.retornaram)}</strong> com retorno no histórico até o fim do período`;
}

function renderVisitorsTable(list){
  const totalPages = Math.max(1, Math.ceil(list.length / state.pageSize));
  state.page = Math.min(state.page, totalPages);
  const start = (state.page-1)*state.pageSize;
  const page = list.slice(start, start+state.pageSize);

  document.getElementById('visitorsTbody').innerHTML = page.map((p,i)=>`
    <tr tabindex="0" role="button" aria-label="Ver detalhes de ${escapeHtml(p.nome)}" data-idx="${start+i}">
      <td><strong>${escapeHtml(p.nome)}</strong>${p.hasReturned?' <span class="badge-status recorrente">Recorrente</span>':' <span class="badge-status novo">Sem retorno registrado</span>'}</td>
      <td>${escapeHtml(p.telefone)||'—'}<br><span class="cell-muted">${escapeHtml(p.email)||''}</span></td>
      <td>${fmtGenero(p.genero)}</td>
      <td>${escapeHtml(p.origem)||'—'}</td>
      <td>${p.cultos.map(c=>`<span class="badge-culto">${escapeHtml(c)}</span>`).join('')}</td>
      <td class="num">${p.visitas}</td>
      <td>${p.ultima}</td>
    </tr>
  `).join('') || `<tr><td colspan="7"><div class="empty-state">Nenhuma pessoa encontrada</div></td></tr>`;

  document.querySelectorAll('#visitorsTbody tr[data-idx]').forEach(tr=>{
    tr.onclick = ()=> showPersonDetail(list[+tr.dataset.idx]);
    tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tr.click();}};
  });

  const pages = [];
  const win = 2;
  for(let p=1;p<=totalPages;p++){
    if(p===1 || p===totalPages || Math.abs(p-state.page)<=win) pages.push(p);
    else if(pages[pages.length-1] !== '…') pages.push('…');
  }
  document.getElementById('pagination').innerHTML = `
    <span>${fmtNum(list.length)} pessoas · página ${state.page}/${totalPages}</span>
    <div class="pages">
      <button class="page-btn neu" id="prevPageBtn" ${state.page<=1?'disabled':''} type="button">${SVG.chevronLeft}</button>
      ${pages.map(p=>p==='…' ? `<span style="padding:0 4px;color:var(--text-muted)">…</span>` : `<button class="page-btn neu${p===state.page?' active':''}" data-page="${p}" type="button">${p}</button>`).join('')}
      <button class="page-btn neu" id="nextPageBtn" ${state.page>=totalPages?'disabled':''} type="button">${SVG.chevronRight}</button>
    </div>
  `;
  document.getElementById('prevPageBtn').onclick = ()=>{ if(state.page>1){ state.page--; renderVisitorsTable(currentPessoasList); } };
  document.getElementById('nextPageBtn').onclick = ()=>{ if(state.page<totalPages){ state.page++; renderVisitorsTable(currentPessoasList); } };
  document.querySelectorAll('#pagination .page-btn[data-page]').forEach(btn=>{
    btn.onclick = ()=>{ state.page = +btn.dataset.page; renderVisitorsTable(currentPessoasList); };
  });
}

function renderVisitorCards(list){
  const visible = list.slice(0, mobileVisibleCount);
  document.getElementById('visitorCards').innerHTML = visible.map((p,i)=>`
    <div class="visitor-card" tabindex="0" role="button" aria-label="Ver detalhes de ${escapeHtml(p.nome)}" data-idx="${i}">
      <div class="vc-top">
        <span class="vc-name">${escapeHtml(p.nome)}</span>
        ${p.hasReturned?'<span class="badge-status recorrente">Recorrente</span>':'<span class="badge-status novo">Sem retorno registrado</span>'}
      </div>
      <div class="vc-meta">${escapeHtml(p.telefone)||'Sem telefone'} · Última visita: ${p.ultima} · ${p.visitas} registro${p.visitas>1?'s':''}</div>
      <div class="vc-cultos">${p.cultos.map(c=>`<span class="badge-culto">${escapeHtml(c)}</span>`).join('')}</div>
    </div>
  `).join('') || `<div class="empty-state">Nenhuma pessoa encontrada</div>`;

  document.querySelectorAll('#visitorCards .visitor-card[data-idx]').forEach(card=>{
    card.onclick = ()=> showPersonDetail(visible[+card.dataset.idx]);
    card.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();card.click();}};
  });
  document.getElementById('loadMoreBtn').classList.toggle('has-more', list.length > mobileVisibleCount);
}

function showPersonDetail(p){
  document.getElementById('personModalName').textContent = p.nome;
  document.getElementById('personModalBody').innerHTML = `
    <div class="person-grid">
      <div class="person-item"><div class="k">Telefone</div><div class="v">${escapeHtml(p.telefone)||'—'}</div></div>
      <div class="person-item"><div class="k">E-mail</div><div class="v">${escapeHtml(p.email)||'—'}</div></div>
      <div class="person-item"><div class="k">Sexo</div><div class="v">${fmtGenero(p.genero)}</div></div>
      <div class="person-item"><div class="k">Como conheceu</div><div class="v">${escapeHtml(p.origem)||'—'}</div></div>
      <div class="person-item"><div class="k">Observação</div><div class="v">${escapeHtml(p.observacao)||'—'}</div></div>
      <div class="person-item"><div class="k">Registros no período</div><div class="v">${p.visitas}</div></div>
      <div class="person-item"><div class="k">Primeira / última</div><div class="v">${p.primeira} → ${p.ultima}</div></div>
    </div>
    <div class="person-item"><div class="k">Histórico de cultos</div>
      <div class="visit-timeline">${p.historico.map(v=>`<span class="visit-tag">${v.data}${v.hora?` ${v.hora}`:''} · ${escapeHtml(v.culto)}</span>`).join('')}</div>
    </div>
  `;
  openModal('personModalOverlay');
}

/* ---------------- EXPORTAR TAB ---------------- */
function csvEscape(v){
  const raw = String(v==null?'':v);
  const s = /^[=+@\-\t\r]/.test(raw) ? "'"+raw : raw;
  return '"' + s.replace(/"/g,'""') + '"';
}
function buildCsv(list){
  const header = ['Nome','Telefone','Email','Sexo','Origem','Observação','Cultos','Registros','Primeira visita','Última visita'];
  const rows = list.map(p => [
    p.nome, p.telefone, p.email, fmtGenero(p.genero), p.origem||'', p.observacao||'',
    p.cultos.join(' | '), p.visitas, p.primeira, p.ultima
  ]);
  const lines = [header, ...rows].map(r => r.map(csvEscape).join(','));
  return '\ufeff' + lines.join('\r\n');
}
function downloadCsv(list){
  const csv = buildCsv(list);
  const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const stamp = new Date().toISOString().slice(0,10);
  a.href = url; a.download = `visitantes-sara-morumbi-sul-${stamp}.csv`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('CSV exportado com sucesso.');
}

function renderExport(s, list){
  document.getElementById('exportCsvDesc').textContent =
    `Baixe ${fmtNum(list.length)} pessoas do filtro atual (${brFromIso(state.dateFrom)||'…'} a ${brFromIso(state.dateTo)||'…'}) em formato CSV.`;
  document.getElementById('exportPreviewBody').innerHTML =
    `<strong>${fmtNum(list.length)}</strong> pessoas · <strong>${fmtNum(s.total)}</strong> registros · <strong>${fmtNum(s.n_cultos)}</strong> cultos no período selecionado.`;
}

function buildPrintReport(s, list){
  const cultoLabel = [...state.cultos].map(id=>CULT_MAP[id]?.nome).filter(Boolean).join(' · ') || 'todos os cultos';
  const rows = list.map(p => `<tr><td>${escapeHtml(p.nome)}</td><td>${escapeHtml(p.telefone)}</td><td>${fmtGenero(p.genero)}</td><td>${p.cultos.map(escapeHtml).join(', ')}</td><td>${p.visitas}</td><td>${p.ultima}</td></tr>`).join('');
  document.getElementById('printReport').innerHTML = `
    <h1>Radar Pastoral · Sara Nossa Terra</h1>
    <p class="pr-meta">Período: ${brFromIso(state.dateFrom)||'…'} a ${brFromIso(state.dateTo)||'…'} · Cultos: ${escapeHtml(cultoLabel)} · Gerado em ${RAW.meta.gerado_em}</p>
    <div class="pr-kpis">
      <div class="pr-kpi"><div class="v">${fmtNum(s.total)}</div><div class="l">Registros</div></div>
      <div class="pr-kpi"><div class="v">${fmtNum(s.unicos)}</div><div class="l">Únicos</div></div>
      <div class="pr-kpi"><div class="v">${fmtNum(s.retornaram)}</div><div class="l">Retornaram</div></div>
      <div class="pr-kpi"><div class="v">${s.taxaRetorno}%</div><div class="l">Taxa de retorno</div></div>
    </div>
    <table>
      <thead><tr><th>Nome</th><th>Telefone</th><th>Sexo</th><th>Cultos</th><th>Registros</th><th>Última visita</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

let toastTimer = null;
function showToast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=> t.classList.remove('show'), 2600);
}

/* ---------------- MODALS ---------------- */
let modalTrigger=null;
function openModal(id){
  if(id==='filterModalOverlay') syncFilterUI();
  modalTrigger=document.activeElement;
  const overlay=document.getElementById(id); overlay.classList.add('open');
  document.body.style.overflow='hidden';
  overlay.querySelector('button,input')?.focus();
}
function closeModal(id){document.getElementById(id).classList.remove('open');document.body.style.overflow='';modalTrigger?.focus();}
document.addEventListener('keydown',e=>{
  const overlay=document.querySelector('.modal-overlay.open');if(!overlay)return;
  if(e.key==='Escape'){e.preventDefault();closeModal(overlay.id);}
  if(e.key==='Tab'){
    const items=[...overlay.querySelectorAll('button,input,[tabindex="0"]')].filter(el=>!el.disabled);
    const first=items[0],last=items.at(-1);
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  }
});

/* ---------------- SCROLL ANIMATIONS ---------------- */
let observer = null;
function setupObserver(){
  const threshold = isMobile() ? 0.1 : 0.15;
  if(observer) observer.disconnect();
  observer = new IntersectionObserver((entries)=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, {threshold});
}
function observeAnimated(root){
  root.querySelectorAll('.animate-in').forEach(el=>{
    if(!el.classList.contains('visible')) observer.observe(el);
  });
}

/* ---------------- PARALLAX (desktop only) ---------------- */
function setupParallax(){
  const bg = document.getElementById('sidebarParallax');
  if(!bg) return;
  let ticking = false;
  window.addEventListener('scroll', () => {
    if(isMobile()) return;
    if(!ticking){
      ticking = true;
      requestAnimationFrame(()=>{
        bg.style.transform = `translateY(${window.scrollY * 0.15}px)`;
        ticking = false;
      });
    }
  }, {passive:true});
}

/* ---------------- TABS ---------------- */
const TAB_TITLES = {visao:'Visão Geral', visitantes:'Visitantes', analises:'Análises', exportar:'Exportar'};
function positionNavIndicator(){
  const active = document.querySelector('.nav-item.active');
  const indicator = document.getElementById('navIndicator');
  if(active && indicator) indicator.style.top = active.offsetTop + 'px';
}
function positionTabbarIndicator(){
  const active = document.querySelector('.tab-btn.active');
  const indicator = document.getElementById('tabbarIndicator');
  if(active && indicator){
    indicator.style.left = active.offsetLeft + 'px';
    indicator.style.width = active.offsetWidth + 'px';
  }
}
function switchTab(tab){
  state.activeTab = tab;
  document.getElementById('workspaceHeading').textContent=TAB_TITLES[tab];
  document.getElementById('workspaceSubtitle').textContent={visao:'Um olhar atento para quem chega e quem caminha com a igreja.',visitantes:'Conheça as pessoas e acompanhe suas visitas.',analises:'Entenda o movimento e a participação nos cultos.',exportar:'Leve os dados para a reunião da equipe pastoral.'}[tab];
  document.querySelectorAll('[data-tab]').forEach(el=>el.setAttribute('aria-current',el.dataset.tab===tab?'page':'false'));
  document.querySelectorAll('.nav-item').forEach(el=>el.classList.toggle('active', el.dataset.tab===tab));
  document.querySelectorAll('.tab-btn').forEach(el=>el.classList.toggle('active', el.dataset.tab===tab));
  document.querySelectorAll('.tab-panel').forEach(el=>el.classList.toggle('active', el.id === 'tab-'+tab));
  document.getElementById('pageTitleMobile').textContent = TAB_TITLES[tab];
  document.getElementById('pageTitleDesktop').textContent = TAB_TITLES[tab];
  positionNavIndicator();
  positionTabbarIndicator();
  requestAnimationFrame(()=> Object.values(charts).forEach(c=>{ try{ c.resize(); }catch(e){} }));
  const panel = document.getElementById('tab-'+tab);
  if(panel) observeAnimated(panel);
}

/* ---------------- FILTERS UI ---------------- */
function syncFilterUI(){
  document.getElementById('dateFromInput').value = state.dateFrom;
  document.getElementById('dateToInput').value = state.dateTo;
  document.querySelectorAll('#cultoChipsModal .chip').forEach(c=> c.classList.toggle('active', state.cultos.has(c.dataset.id)));
  document.querySelectorAll('.preset-chip').forEach(c=> c.classList.toggle('active', c.dataset.preset === state.preset));
  document.querySelectorAll('#retornoChipsModal .chip').forEach(c=> c.classList.toggle('active', c.dataset.retorno === state.retorno));
  document.querySelectorAll('#statusFilterChips .chip').forEach(c=> c.classList.toggle('active', c.dataset.retorno === state.retorno));
}

function applyPreset(preset){
  const fim = isoFromBr(RAW.meta.periodo_fim) || new Date().toISOString().slice(0,10);
  const inicio = isoFromBr(RAW.meta.periodo_inicio) || fim;
  if(preset === 'all'){
    state.dateFrom = inicio; state.dateTo = fim;
  } else if(preset === '30' || preset === '90'){
    const days = preset === '30' ? 30 : 90;
    const end = new Date(fim+'T00:00:00');
    const start = new Date(end); start.setDate(start.getDate() - days + 1);
    const startIso = start.toISOString().slice(0,10);
    state.dateFrom = startIso < inicio ? inicio : startIso;
    state.dateTo = fim;
  } else if(preset === 'year'){
    const y = fim.slice(0,4);
    state.dateFrom = `${y}-01-01` < inicio ? inicio : `${y}-01-01`;
    state.dateTo = fim;
  }
  state.preset = preset;
  state.page = 1; mobileVisibleCount = MOBILE_PAGE_STEP;
  syncFilterUI();
  renderAll();
}

function buildPeriodChips(container, className){
  const presets = [{id:'all', label:'Tudo'}, {id:'30', label:'30 dias'}, {id:'90', label:'90 dias'}, {id:'year', label:'Ano dos dados'}];
  container.innerHTML = presets.map(p=>`<button class="chip preset-chip${p.id===state.preset?' active':''}" data-preset="${p.id}" type="button">${p.label}</button>`).join('');
  container.querySelectorAll('.preset-chip').forEach(btn=>{
    btn.onclick = ()=> applyPreset(btn.dataset.preset);
  });
}

/* ---------------- RENDER ALL ---------------- */
function renderAll(){
  const regs = filterRegistros();
  const participacao = filterParticipacao();
  const s = computeStats(regs, participacao);

  renderLead(s);
  renderKpis(s);
  renderInsights(s);
  renderCharts(s);
  renderPastoralOverview(s);
  renderPastoralCharts(s);

  const list = filteredPessoas(s);
  currentPessoasList = list;
  renderVisitorsSummary(s, list);
  renderVisitorsTable(list);
  renderVisitorCards(list);
  renderExport(s, list);
  buildPrintReport(s, list);

  document.getElementById('sidebarFooter').innerHTML =
    `${escapeHtml(RAW.meta.igreja)}<br>${fmtNum(s.total)} registros · gerado em ${RAW.meta.gerado_em}`;

  observeAnimated(document.getElementById('content'));
}

/* ---------------- INIT ---------------- */
(function init(){
  setupObserver();
  document.getElementById('quickFilter').onclick=()=>openModal('filterModalOverlay');
  document.getElementById('goAnalyses').onclick=()=>switchTab('analises');

  buildPeriodChips(document.getElementById('periodPresetsDesktop'));
  buildPeriodChips(document.getElementById('periodChipsMobile'));

  document.getElementById('cultoChipsModal').innerHTML = CULTOS.map(c=>`
    <button class="chip active" data-id="${c.id}" type="button" title="${c.nota||''}"><span class="dot"></span>${c.dia} · ${c.nome}</button>
  `).join('');
  document.getElementById('cultoChipsModal').onclick = e=>{
    const chip = e.target.closest('.chip'); if(!chip) return;
    const id = chip.dataset.id;
    chip.classList.toggle('active');
    if(!document.querySelector('#cultoChipsModal .chip.active')) chip.classList.add('active');
  };

  const retornoOptions = [{id:'all', label:'Todos'}, {id:'novos', label:'Novos no período'}, {id:'retorno', label:'Com retorno registrado'}];
  document.getElementById('retornoChipsModal').innerHTML = retornoOptions.map(o=>`<button class="chip${o.id==='all'?' active':''}" data-retorno="${o.id}" type="button">${o.label}</button>`).join('');
  document.getElementById('retornoChipsModal').onclick = e=>{
    const chip = e.target.closest('.chip'); if(!chip) return;
    document.querySelectorAll('#retornoChipsModal .chip').forEach(c=>c.classList.remove('active'));
    chip.classList.add('active');
  };
  document.getElementById('statusFilterChips').innerHTML = retornoOptions.map(o=>`<button class="chip${o.id==='all'?' active':''}" data-retorno="${o.id}" type="button">${o.label}</button>`).join('');
  document.getElementById('statusFilterChips').onclick = e=>{
    const chip = e.target.closest('.chip'); if(!chip) return;
    document.querySelectorAll('#statusFilterChips .chip').forEach(c=>c.classList.remove('active'));
    chip.classList.add('active');
    state.retorno = chip.dataset.retorno; state.page = 1; mobileVisibleCount = MOBILE_PAGE_STEP;
    syncFilterUI();
    renderAll();
  };

  syncFilterUI();

  // Navigation
  document.getElementById('sideNav').addEventListener('click', e=>{
    const btn = e.target.closest('.nav-item'); if(!btn) return;
    switchTab(btn.dataset.tab);
  });
  document.getElementById('bottomTabbar').addEventListener('click', e=>{
    const btn = e.target.closest('.tab-btn'); if(!btn) return;
    switchTab(btn.dataset.tab);
  });

  // Search
  document.getElementById('searchInput').oninput = e=>{
    state.search = e.target.value; state.page = 1; mobileVisibleCount = MOBILE_PAGE_STEP;
    document.getElementById('clearSearchBtn').classList.toggle('show', !!e.target.value);
    renderAll();
  };
  document.getElementById('clearSearchBtn').onclick = ()=>{
    document.getElementById('searchInput').value = ''; state.search = ''; state.page = 1; mobileVisibleCount = MOBILE_PAGE_STEP;
    document.getElementById('clearSearchBtn').classList.remove('show');
    renderAll();
  };

  // Load more (mobile)
  document.getElementById('loadMoreBtn').onclick = ()=>{
    mobileVisibleCount += MOBILE_PAGE_STEP;
    renderVisitorCards(currentPessoasList);
  };

  // Filter modal
  document.getElementById('mobileFilterBtn').onclick = ()=> openModal('filterModalOverlay');
  document.getElementById('desktopFilterBtn').onclick = ()=> openModal('filterModalOverlay');
  document.getElementById('closeFilterModal').onclick = ()=> closeModal('filterModalOverlay');
  document.getElementById('filterModalOverlay').addEventListener('click', e=>{ if(e.target.id==='filterModalOverlay') closeModal('filterModalOverlay'); });
  document.getElementById('btnApplyFilters').onclick = ()=>{
    const from=document.getElementById('dateFromInput').value;
    const to=document.getElementById('dateToInput').value;
    if(from&&to&&from>to){showToast('A data inicial deve ser anterior à data final.');return;}
    state.dateFrom = document.getElementById('dateFromInput').value;
    state.dateTo = document.getElementById('dateToInput').value;
    const activeRetorno = document.querySelector('#retornoChipsModal .chip.active');
    state.retorno = activeRetorno ? activeRetorno.dataset.retorno : 'all';
    state.cultos=new Set([...document.querySelectorAll('#cultoChipsModal .chip.active')].map(c=>c.dataset.id));
    state.preset = 'custom'; state.page = 1; mobileVisibleCount = MOBILE_PAGE_STEP;
    syncFilterUI();
    renderAll();
    closeModal('filterModalOverlay');
  };
  document.getElementById('btnClearFilters').onclick = ()=>{
    state.cultos = new Set(CULTOS.map(c => c.id));
    state.search=''; state.retorno='all'; state.page=1; mobileVisibleCount = MOBILE_PAGE_STEP;
    document.getElementById('searchInput').value = '';
    document.getElementById('clearSearchBtn').classList.remove('show');
    applyPreset('all');
    closeModal('filterModalOverlay');
  };

  // Person modal
  document.getElementById('closePersonModal').onclick = ()=> closeModal('personModalOverlay');
  document.getElementById('personModalOverlay').addEventListener('click', e=>{ if(e.target.id==='personModalOverlay') closeModal('personModalOverlay'); });

  // Export
  document.getElementById('btnExportCsv').onclick = ()=> downloadCsv(currentPessoasList);
  document.getElementById('btnPrint').onclick = ()=>{ buildPrintReport(computeStats(filterRegistros(), filterParticipacao()), currentPessoasList); window.print(); };

  window.addEventListener('resize', ()=>{ setupObserver(); observeAnimated(document.getElementById('content')); positionNavIndicator(); positionTabbarIndicator(); });

  renderAll();
  positionNavIndicator();
  positionTabbarIndicator();
})();
