const assert = require('node:assert/strict');
const vm = require('node:vm');
const inputs = ['apiKey', 'apiSecret', 'accessToken', 'accessTokenSecret'].map(name => ({dataset:{name},value:`fake-${name}`,disabled:false,focus(){}}));
const button = {};
const reveal = {pressed:'false',setAttribute(_,value){this.pressed=value;},getAttribute(){return this.pressed;},addEventListener(_,fn){this.click=fn;}};
let submit;
const form = {querySelectorAll:()=>inputs,querySelector:()=>button,addEventListener:(_,fn)=>submit=fn,remove(){this.removed=true;}};
const message = {classList:{toggle(){}},focus(){}};
const intro = {}, heading = {};
let payload;
const context = {document:{getElementById:id=>({form,message,intro,reveal})[id],querySelector:()=>heading},location:{pathname:'/r/test'},AbortController,setTimeout,clearTimeout,
  fetch:async (_url,options)=>{payload=JSON.parse(JSON.parse(options.body).secret);assert.ok(inputs.every(i=>i.value===''&&i.disabled&&i.type==='password'));return {ok:true};}};
vm.runInNewContext(require('node:fs').readFileSync(0,'utf8'),context);
reveal.click();
assert.ok(inputs.every(i=>i.type==='text'));
(async()=>{await submit({preventDefault(){}});assert.deepEqual(payload,Object.fromEntries(inputs.map(i=>[i.dataset.name,`fake-${i.dataset.name}`])));assert.ok(form.removed);console.log('ok');})().catch(e=>{console.error(e);process.exitCode=1;});
