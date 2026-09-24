// A deterministic DOM/clock harness to detect node churn and idle scheduling.
export function playerDom(data) {
  const counts = {elements:0,textNodes:0,replacements:0,layoutReads:0};
  const events = new Map(), timers = new Map();
  let now = 0, nextTimer = 0;
  function textNode(value) {
    counts.textNodes++;
    return {data:value,get textContent(){return this.data;},set textContent(value){this.data=value;}};
  }
  function element(fragment = false) {
    counts.elements++;
    return {fragment,style:{},children:[],value:0,checked:true,dataset:{},
      append(child){this.children.push(child);},
      replaceChildren(...items){counts.replacements++;this.children=items.flatMap(x=>x.fragment?x.children:[x]);},
      get textContent(){return this.children.map(x=>x.textContent).join('');},
      set textContent(value){this.children=value?[textNode(value)]:[];},
      get clientWidth(){counts.layoutReads++;return 800;},
      get clientHeight(){counts.layoutReads++;return 600;},
      get scrollWidth(){counts.layoutReads++;return 100;},
      get scrollHeight(){counts.layoutReads++;return 80;},
      remove(){this.removed=true;}};
  }
  const elements=new Map();
  const get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  get('data').textContent=JSON.stringify(data);get('speed').value=1;
  let embedded=false;
  const document={getElementById:get,createElement:()=>element(),createDocumentFragment:()=>element(true),
    createTextNode:textNode,hidden:false,
    addEventListener:(name,fn)=>events.set(name,fn),
    body:{style:{},classList:{add(){embedded=true;}}},fonts:{ready:Promise.resolve()}};
  return {document,get,element,counts,timers,events,get embedded(){return embedded;},
    globals:{document,window:{addEventListener:(name,fn)=>events.set(name,fn)},location:{search:''},
      performance:{now:()=>now},
      setTimeout:(fn,delay)=>{const id=++nextTimer;timers.set(id,{fn,at:now+delay});return id;},
      clearTimeout:id=>timers.delete(id)},
    elapse(ms){
      const end=now+ms;
      while(timers.size){
        const [id,timer]=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];
        if(timer.at>end)break;
        now=timer.at;timers.delete(id);timer.fn();
      }
      now=end;
    },
    install(){const previous=Object.fromEntries(Object.keys(this.globals).map(k=>[k,globalThis[k]]));
      Object.assign(globalThis,this.globals);return()=>Object.assign(globalThis,previous);}
  };
}
