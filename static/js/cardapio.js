// ════ CONFIGURAÇÃO ════════════════════════════════════════════
// Quando integrar com Flask, substitua esta linha:
//   const WHATSAPP = '{{ restaurante.whatsapp }}';
// E os dados de cats:
//   const cats = {{ categorias | tojson }};
const WHATSAPP = '5511999999999';

const cats = [
  { id:'lanches', nome:'Lanches', emoji:'🍔', prods:[
    { id:1, nome:'X-Burguer', desc:'Pão brioche, carne 180g, queijo cheddar e molho especial da casa', preco:22.90, emoji:'🍔',
      ads:[{id:'bacon',nome:'Bacon crocante',preco:4},{id:'duplo',nome:'Carne dupla',preco:8},{id:'ovo',nome:'Ovo frito',preco:3},{id:'catupiry',nome:'Catupiry',preco:4}]},
    { id:2, nome:'X-Frango', desc:'Frango grelhado, alface, tomate e maionese caseira', preco:20.90, emoji:'🐔',
      ads:[{id:'bacon',nome:'Bacon crocante',preco:4},{id:'queijo',nome:'Queijo extra',preco:3}]},
    { id:3, nome:'X-Tudo', desc:'Carne, frango, bacon, ovo, queijo e muito mais', preco:32.90, emoji:'🥪', ads:[]},
    { id:4, nome:'Hot Dog', desc:'Salsicha grossa, purê de batata e molho especial', preco:16.90, emoji:'🌭',
      ads:[{id:'batata',nome:'Batata palha',preco:2},{id:'milho',nome:'Milho verde',preco:2}]},
  ]},
  { id:'marmitas', nome:'Marmitas', emoji:'🍱', prods:[
    { id:5, nome:'Marmita P', desc:'Arroz, feijão, proteína grelhada e salada fresca', preco:18.90, emoji:'🍱',
      ads:[{id:'extra',nome:'Proteína extra',preco:8},{id:'farofa',nome:'Farofa',preco:3},{id:'macarrao',nome:'Macarrão',preco:3}]},
    { id:6, nome:'Marmita G', desc:'Arroz, feijão, proteína grelhada, salada e acompanhamento', preco:25.90, emoji:'🥘',
      ads:[{id:'extra',nome:'Proteína extra',preco:8},{id:'farofa',nome:'Farofa',preco:3}]},
    { id:7, nome:'Frango Grelhado', desc:'Peito de frango grelhado com arroz e legumes frescos', preco:24.90, emoji:'🍗', ads:[]},
  ]},
  { id:'bebidas', nome:'Bebidas', emoji:'🥤', prods:[
    { id:8, nome:'Refrigerante Lata', desc:'Coca-Cola, Guaraná, Fanta (350ml)', preco:7.00, emoji:'🥤', ads:[]},
    { id:9, nome:'Suco Natural', desc:'Laranja, Limão, Maracujá ou Abacaxi (400ml)', preco:10.00, emoji:'🧃', ads:[]},
    { id:10, nome:'Água Mineral', desc:'Com ou sem gás (500ml)', preco:4.50, emoji:'💧', ads:[]},
    { id:11, nome:'Cerveja Long Neck', desc:'Heineken, Budweiser ou Stella (330ml)', preco:12.00, emoji:'🍺', ads:[]},
  ]},
];

// ════ ESTADO ═════════════════════════════════════════════════
let carrinho = [];
let pAtual = null, qtd = 1, adsSel = [];
let pgtoSel = 'pix';
let catAtiva = 'todos';

// ════ UTILS ══════════════════════════════════════════════════
function getProd(id){ for(const c of cats){const p=c.prods.find(x=>x.id===id);if(p)return p;} }
function fmt(v){ return 'R$ '+v.toFixed(2).replace('.',','); }
function showToast(msg){ const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200); }
function qtdNoCarrinho(id){ return carrinho.filter(i=>i.id===id).reduce((a,i)=>a+i.qtd,0); }

// ════ CATEGORIAS ═════════════════════════════════════════════
function renderCats(){
  const w=document.getElementById('catsWrap');
  w.innerHTML=`<button class="cat-btn ativo" onclick="filtrarCat('todos',this)">Todos</button>`
    +cats.map(c=>`<button class="cat-btn" onclick="filtrarCat('${c.id}',this)">${c.emoji} ${c.nome}</button>`).join('');
}

function filtrarCat(id,btn){
  catAtiva=id;
  document.querySelectorAll('.cat-btn').forEach(b=>b.classList.remove('ativo'));
  btn.classList.add('ativo');
  renderProds();
  if(id!=='todos'){
    setTimeout(()=>{const el=document.getElementById('sec-'+id);if(el)el.scrollIntoView({behavior:'smooth',block:'start'});},60);
  }
}

// ════ PRODUTOS ═══════════════════════════════════════════════
function renderProds(busca=''){
  const ct=document.getElementById('conteudo');
  const lista=catAtiva==='todos'?cats:cats.filter(c=>c.id===catAtiva);
  let html='';
  lista.forEach(cat=>{
    const prods=busca?cat.prods.filter(p=>p.nome.toLowerCase().includes(busca.toLowerCase())):cat.prods;
    if(!prods.length)return;
    html+=`<div class="secao" id="sec-${cat.id}">
      <div class="secao-titulo">${cat.emoji} ${cat.nome}</div>
      <div class="cards-grid">`;
    prods.forEach(p=>{
      const qc=qtdNoCarrinho(p.id);
      html+=`
        <div class="card ${qc>0?'sel':''}" onclick="abrirModal(${p.id})">
          <div class="card-foto">${p.emoji}</div>
          <div class="card-badge ${qc>0?'v':''}">${qc}</div>
          <div class="card-body">
            <div class="card-nome">${p.nome}</div>
            <div class="card-desc">${p.desc}</div>
            <div class="card-foot">
              <div class="card-preco">${fmt(p.preco)}</div>
              <button class="card-add" onclick="quickAdd(event,${p.id})">+</button>
            </div>
          </div>
        </div>`;
    });
    html+=`</div></div>`;
  });
  ct.innerHTML=html||'<div class="vazio"><div class="vazio-emoji">🔍</div><div class="vazio-txt">Nenhum item encontrado</div></div>';
}

function quickAdd(e,id){
  e.stopPropagation();
  const p=getProd(id);
  if(p.ads.length>0){abrirModal(id);return;}
  carrinho.push({id:p.id,nome:p.nome,preco:p.preco,qtd:1,ads:[],obs:'',emoji:p.emoji});
  renderProds(document.getElementById('buscaInput').value);
  atualizarFooter();
  showToast('✓ '+p.nome+' adicionado!');
}

// ════ MODAL ═══════════════════════════════════════════════════
function abrirModal(id){
  pAtual=getProd(id); qtd=1; adsSel=[];
  const foto=document.getElementById('mFoto');
  foto.innerHTML=`<span style="font-size:90px">${pAtual.emoji}</span><button class="modal-fechar" onclick="fecharModal()">✕</button>`;
  document.getElementById('mNome').textContent=pAtual.nome;
  document.getElementById('mDesc').textContent=pAtual.desc;
  document.getElementById('mPreco').textContent=fmt(pAtual.preco);
  document.getElementById('qtdNum').textContent=1;
  document.getElementById('obsInput').value='';

  const area=document.getElementById('adsArea');
  if(pAtual.ads.length>0){
    area.innerHTML=`
      <div class="ads-titulo" style="margin-top:8px">Adicionais disponíveis</div>
      <div class="ads-sub">Toque para adicionar</div>
      <div class="ads-grid">
        ${pAtual.ads.map(a=>`
          <div class="ad-chip" id="ad-${a.id}" onclick="toggleAd('${a.id}')">
            <div class="ad-chip-nome">${a.nome}</div>
            <div class="ad-chip-preco">+${fmt(a.preco)}</div>
          </div>`).join('')}
      </div>`;
  } else {
    area.innerHTML='';
  }

  atualizarTotalModal();
  document.getElementById('overlay').classList.add('on');
  document.body.style.overflow='hidden';
  setTimeout(()=>document.getElementById('modal').scrollTop=0,50);
}

function fecharModal(){ document.getElementById('overlay').classList.remove('on'); document.body.style.overflow=''; }
function fecharOverlay(e){ if(e.target===document.getElementById('overlay'))fecharModal(); }

function dQtd(d){
  qtd=Math.max(1,qtd+d);
  document.getElementById('qtdNum').textContent=qtd;
  atualizarTotalModal();
}

function toggleAd(id){
  const idx=adsSel.indexOf(id);
  const chip=document.getElementById('ad-'+id);
  if(idx===-1){adsSel.push(id);chip.classList.add('on');}
  else{adsSel.splice(idx,1);chip.classList.remove('on');}
  atualizarTotalModal();
}

function calcTotal(){
  if(!pAtual)return 0;
  let t=pAtual.preco;
  adsSel.forEach(id=>{const a=pAtual.ads.find(x=>x.id===id);if(a)t+=a.preco;});
  return t*qtd;
}

function atualizarTotalModal(){
  document.getElementById('btnModalTotal').textContent=fmt(calcTotal());
}

function addCarrinho(){
  const obs=document.getElementById('obsInput').value.trim();
  const adObjs=adsSel.map(id=>pAtual.ads.find(a=>a.id===id));
  carrinho.push({id:pAtual.id,nome:pAtual.nome,preco:pAtual.preco,qtd,ads:adObjs,obs,emoji:pAtual.emoji});
  fecharModal();
  renderProds(document.getElementById('buscaInput').value);
  atualizarFooter();
  showToast('✓ '+pAtual.nome+' adicionado!');
}

// ════ FOOTER ══════════════════════════════════════════════════
function atualizarFooter(){
  const qtdTotal=carrinho.reduce((a,i)=>a+i.qtd,0);
  const btn=document.getElementById('footerBtn');
  if(qtdTotal===0){btn.classList.remove('v');return;}

  const agrup={};
  carrinho.forEach(i=>{agrup[i.nome]=(agrup[i.nome]||0)+i.qtd;});
  const linhas=Object.entries(agrup).map(([n,q])=>`${q}x ${n}`);

  const total=calcTotalCarrinho();
  document.getElementById('fBadge').textContent=qtdTotal;
  document.getElementById('fLinhas').innerHTML=
    linhas.slice(0,2).map(l=>`<div class="footer-linha">${l}</div>`).join('')
    +(linhas.length>2?`<div class="footer-linha">+${linhas.length-2} mais</div>`:'');
  document.getElementById('fTotalRodape').textContent=fmt(total);
  btn.classList.add('v');
}

function calcTotalCarrinho(){
  return carrinho.reduce((a,i)=>{
    let t=i.preco*i.qtd;
    i.ads.forEach(ad=>{t+=ad.preco*i.qtd;});
    return a+t;
  },0);
}

// ════ NAVEGAÇÃO ═══════════════════════════════════════════════
function irCarrinho(){
  if(carrinho.length===0)return;
  renderCarrinho();
  document.getElementById('telaCardapio').classList.remove('ativa');
  document.getElementById('telaCarrinho').classList.add('ativa');
  window.scrollTo(0,0);
}

function voltarCardapio(){
  document.getElementById('telaCarrinho').classList.remove('ativa');
  document.getElementById('telaCardapio').classList.add('ativa');
}

// ════ CARRINHO ════════════════════════════════════════════════
function renderCarrinho(){
  const el=document.getElementById('carrItens');
  if(carrinho.length===0){
    el.innerHTML='<div class="vazio"><div class="vazio-emoji">🛒</div><div class="vazio-txt">Carrinho vazio</div></div>';
    return;
  }
  el.innerHTML=carrinho.map((item,idx)=>{
    const subtotal=item.preco*item.qtd+item.ads.reduce((a,ad)=>a+ad.preco*item.qtd,0);
    const adsStr=item.ads.length>0?item.ads.map(a=>a.nome).join(', '):'';
    return `
      <div class="carr-item">
        <div class="carr-item-emoji">${item.emoji}</div>
        <div class="carr-item-info">
          <div class="carr-item-nome">${item.qtd}x ${item.nome}</div>
          ${adsStr?`<div class="carr-item-ads">+ ${adsStr}</div>`:''}
          ${item.obs?`<div class="carr-item-obs">"${item.obs}"</div>`:''}
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
          <div class="carr-item-preco">${fmt(subtotal)}</div>
          <button class="carr-remover" onclick="removerItem(${idx})">🗑</button>
        </div>
      </div>`;
  }).join('');
  renderResumo();
}

function removerItem(idx){
  carrinho.splice(idx,1);
  renderCarrinho();
  atualizarFooter();
  if(carrinho.length===0){voltarCardapio();}
}

function renderResumo(){
  const total=calcTotalCarrinho();
  document.getElementById('carrResumo').innerHTML=`
    <div class="resumo-linha"><span>Subtotal</span><span>${fmt(total)}</span></div>
    <div class="resumo-linha"><span>Entrega</span><span>A combinar</span></div>
    <div class="resumo-total"><span>Total</span><span>${fmt(total)}</span></div>`;
}

function selecionarPgto(p){
  pgtoSel=p;
  document.querySelectorAll('.pgto-btn').forEach(b=>b.classList.remove('on'));
  document.getElementById('pg-'+p).classList.add('on');
  document.getElementById('trocoWrap').style.display=p==='dinheiro'?'block':'none';
}

// ════ FINALIZAR ═══════════════════════════════════════════════
function finalizarPedido(){
  const nome=document.getElementById('cNome').value.trim();
  const tel=document.getElementById('cTel').value.trim();
  const end=document.getElementById('cEnd').value.trim();
  const troco=document.getElementById('cTroco').value.trim();

  if(!nome){showToast('⚠️ Informe seu nome!');return;}
  if(!tel){showToast('⚠️ Informe seu telefone!');return;}

  const pgtoNomes={pix:'Pix',dinheiro:'Dinheiro',credito:'Cartão de Crédito',debito:'Cartão de Débito'};

  let msg=`*🍽 Novo Pedido — Comanda Digital*\n\n`;
  msg+=`👤 *Cliente:* ${nome}\n`;
  msg+=`📞 *Telefone:* ${tel}\n`;
  if(end) msg+=`📍 *Endereço:* ${end}\n`;
  msg+=`\n*🛒 Itens do pedido:*\n`;

  carrinho.forEach(item=>{
    const sub=item.preco*item.qtd+item.ads.reduce((a,ad)=>a+ad.preco*item.qtd,0);
    msg+=`\n• ${item.qtd}x *${item.nome}* — ${fmt(sub)}`;
    if(item.ads.length>0) msg+=`\n  ↳ Adicionais: ${item.ads.map(a=>a.nome).join(', ')}`;
    if(item.obs) msg+=`\n  ↳ Obs: _${item.obs}_`;
  });

  msg+=`\n\n💰 *Total: ${fmt(calcTotalCarrinho())}*`;
  msg+=`\n💳 *Pagamento:* ${pgtoNomes[pgtoSel]}`;
  if(pgtoSel==='dinheiro'&&troco) msg+=`\n🔄 *Troco para:* R$ ${troco}`;
  msg+=`\n\n_Pedido enviado pelo Comanda Digital_`;

  const url=`https://wa.me/${WHATSAPP}?text=${encodeURIComponent(msg)}`;
  window.open(url,'_blank');
}

// ════ BUSCA ═══════════════════════════════════════════════════
document.getElementById('buscaInput').addEventListener('input',function(){
  renderProds(this.value);
});

// ════ INIT ════════════════════════════════════════════════════
renderCats();
renderProds();