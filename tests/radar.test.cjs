const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..');
const source=fs.readFileSync(path.join(root,'radar.js'),'utf8');
const raw=JSON.parse(fs.readFileSync(path.join(root,'dashboard-data.json'),'utf8'));
function harness(data){
  const context=vm.createContext({
    document:{getElementById:()=>({textContent:JSON.stringify(data)}),addEventListener:()=>{}},
    window:{Chart:null},console
  });
  vm.runInContext(source.split('(function init(){')[0],context);
  vm.runInContext('syncFilterUI=()=>{};renderAll=()=>{};',context);
  return code=>vm.runInContext(code,context);
}
test('current dataset retains all 817 records and attendance totals',()=>{
  const run=harness(raw);
  const s=run('computeStats(filterRegistros(),filterParticipacao())');
  assert.equal(s.total,817);assert.equal(s.unicos,794);
  assert.equal(s.totalMembros,10579);assert.equal(s.totalCriancas,1465);
  assert.equal(s.participacao.length,26);
  assert.equal(s.novos_por_mes.reduce((sum,m)=>sum+m.count,0),s.newPeople);
});
const cultos=[{id:'morning',nome:'Manhã'},{id:'night',nome:'Noite'}];
function record(name,date,culto='morning',hour='10:00'){
  return {nome:name,telefone:name,telefone_norm:name,email:'',data_iso:date,data:date.split('-').reverse().join('/'),culto_id:culto,culto:culto==='morning'?'Manhã':'Noite',weekday:'Domingo',hora:hour,genero:null,origem:null};
}
const fixture={cultos,meta:{periodo_inicio:'01/08/2026',periodo_fim:'08/09/2026'},registros:[
  record('A','2026-08-23'),record('A','2026-09-06'),
  record('B','2026-09-06'),record('B','2026-09-06','morning','11:00'),
  record('C','2026-09-06'),record('C','2026-09-06','night','19:00'),
  record('D','2026-08-30','night'),record('D','2026-09-06')
],participacao:[]};
test('first visits use full history and repeat registrations are not returns',()=>{
  const run=harness(fixture);
  run("state.dateFrom='2026-09-01';state.dateTo='2026-09-08'");
  const s=run('computeStats(filterRegistros(),[])');
  assert.equal(s.total,6);assert.equal(s.unicos,4);assert.equal(s.newPeople,2);
  assert.equal(s.returningPeople,3); // A/D returned on new dates; C attended two cultos.
  assert.equal(s.pessoas.find(p=>p.nome==='B').hasReturned,false);
  assert.equal(s.monthlyPeople[0].new,2);assert.equal(s.monthlyPeople[0].returning,2);
  run("state.retorno='novos'");
  assert.equal(run('filteredPessoas(computeStats(filterRegistros(),[])).length'),2);
});
test('a culto filter does not invent first visits or future returns',()=>{
  const run=harness(fixture);
  run("state.dateFrom='2026-09-01';state.cultos=new Set(['morning'])");
  assert.equal(run('computeStats(filterRegistros(),[]).newPeople'),2);
  run("state.dateFrom='2026-08-01';state.dateTo='2026-08-31'");
  assert.equal(run('computeStats(filterRegistros(),[]).returningPeople'),0);
});
test('partial-month filters classify earlier first visits as returning',()=>{
  const data={...fixture,registros:[record('A','2026-09-01'),record('A','2026-09-06')]};
  const run=harness(data);run("state.dateFrom='2026-09-05'");
  const s=run('computeStats(filterRegistros(),[])');
  assert.equal(s.newPeople,0);assert.equal(s.monthlyPeople[0].new,0);
});
test('30-day preset includes exactly 30 dates',()=>{
  const run=harness(raw);run("applyPreset('30')");
  assert.equal(run('state.dateFrom'),'2026-08-10');assert.equal(run('state.dateTo'),'2026-09-08');
});
test('empty range and attendance-only range are safe',()=>{
  const run=harness(raw);run("state.dateFrom='2030-01-01';state.dateTo='2030-01-02'");
  const s=run('computeStats(filterRegistros(),filterParticipacao())');
  for(const k of ['total','unicos','newPeople','returningPeople','taxaRetorno']) assert.equal(s[k],0);
  assert.equal(run('computeStats([],[{member_count:42,children_count:0}]).totalMembros'),42);
});
test('CSV protects literal spreadsheet formulas and quoted fields',()=>{
  const run=harness(raw);
  assert.equal(run('csvEscape("=1+1")'),'"\'=1+1"');
  assert.equal(run('csvEscape(\'Nome "teste"\')'),'"Nome ""teste"""');
});
test('build outputs share the same data and valid executable scripts',()=>{
  const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
  assert.equal(html,fs.readFileSync(path.join(root,'dashboard-visitantes.html'),'utf8'));
  const payload=html.match(/<script id="dashboard-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
  assert.deepEqual(JSON.parse(payload),raw);
  assert(!/__STYLE__|__APPJS__|__DATA_JSON__|__CHARTJS__/.test(html));
  for(const [,script] of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(script);
  const markup=html.replace(/(<script[^>]*>)[\s\S]*?<\/script>/g,'$1</script>');
  const ids=[...markup.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(new Set(ids).size,ids.length,'duplicate element IDs');
  for(const [,id] of source.matchAll(/getElementById\('([^']+)'\)/g)) {
    assert(ids.includes(id)||source.includes(`id="${id}"`),`missing target ${id}`);
  }
});
