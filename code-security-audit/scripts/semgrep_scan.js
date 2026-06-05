#!/usr/bin/env node
/** code-security-audit scanner: Semgrep first, builtin fallback when unavailable. */
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const SKILL_ROOT = path.resolve(__dirname, '..');
const LOCAL_SEMGREP = path.join(SKILL_ROOT, '.venv', 'bin', 'semgrep');
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

const DEFAULT_EXCLUDES = ['node_modules','.git','.svn','.hg','dist','build','coverage','.next','.nuxt','vendor','__pycache__','.venv','venv','env','target','.cache','.npm','.pnpm-store'];
const TEXT_EXTENSIONS = new Set(['.js','.jsx','.ts','.tsx','.mjs','.cjs','.json','.json5','.py','.sh','.bash','.zsh','.fish','.ps1','.java','.go','.rs','.php','.rb','.cs','.c','.cc','.cpp','.h','.hpp','.yml','.yaml','.toml','.ini','.conf','.config','.env','.md','.txt','.sql','.xml','.html','.css','.scss','.properties','.pem','.key','.crt','.cert']);
const CODE_EXTENSIONS = new Set(['.js','.jsx','.ts','.tsx','.mjs','.cjs','.py','.sh','.bash','.zsh','.fish','.ps1','.java','.go','.rs','.php','.rb','.cs','.c','.cc','.cpp','.h','.hpp','.sql']);
const CONFIG_EXTENSIONS = new Set(['.json','.json5','.yml','.yaml','.toml','.ini','.conf','.config','.env','.properties']);
const BUILTIN_RULES = [
  {id:'builtin.secrets.generic-assignment', target:'code-config', severity:'CRITICAL', message:'疑似敏感凭据硬编码。请改用环境变量、密钥管理系统或 OpenClaw 安全配置，并立即轮换已暴露凭据。', fix:'删除硬编码密钥，改为 process.env/配置中心/Secret Manager；提交前确认历史记录中没有残留。', regex:/\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|private[_-]?key|client[_-]?secret)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}/i},
  {id:'builtin.secrets.private-key', severity:'BLOCKER', message:'发现私钥块标记。私钥不应出现在代码仓库或普通配置目录中。', fix:'移除私钥文件，放入受控密钥存储；若已提交或同步过，立即轮换密钥。', regex:/-----BEGIN (RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----/},
  {id:'builtin.crypto.md5-sha1', target:'code', severity:'MAJOR', message:'发现 MD5/SHA1 等弱哈希算法。用于安全场景时存在碰撞风险。', fix:'密码存储使用 Argon2/bcrypt/scrypt；完整性校验至少使用 SHA-256/HMAC-SHA256。', regex:/\b(md5|sha1)\s*\(|createHash\(\s*['\"](?:md5|sha1)['\"]\s*\)|hashlib\.(?:md5|sha1)\s*\(/i},
  {id:'builtin.command-injection.shell-exec', target:'code', severity:'CRITICAL', message:'发现 shell 命令执行入口。若拼接了外部输入，可能导致命令注入。', fix:'优先使用 execFile/spawn 参数数组；校验/白名单化输入；避免 shell:true 和字符串拼接。', regex:/\b(execSync|exec|popen|system|subprocess\.Popen|os\.system|shell_exec|passthru)\s*\(/i},
  {id:'builtin.code-injection.eval', target:'code', severity:'CRITICAL', message:'发现 eval/new Function 等动态代码执行，可能导致代码注入。', fix:'移除动态执行；使用解析器、白名单分发表或安全模板引擎替代。', regex:/\b(eval|Function)\s*\(/i},
  {id:'builtin.sql-injection.concat', target:'code', severity:'CRITICAL', message:'疑似 SQL 字符串拼接。若包含外部输入，可能导致 SQL 注入。', fix:'使用参数化查询/预编译语句；禁止把用户输入直接拼接进 SQL。', regex:/(SELECT|INSERT|UPDATE|DELETE)\s+[^\n]*(\+|\$\{|%s|\.format\()/i},
  {id:'builtin.insecure-tls-disable', target:'code-config', severity:'CRITICAL', message:'发现关闭 TLS/证书校验的配置。生产环境会导致中间人攻击风险。', fix:'启用证书校验；仅在本地调试临时使用，并加环境隔离。', regex:/(NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0|rejectUnauthorized\s*:\s*false|verify\s*=\s*False|insecureSkipVerify\s*:\s*true)/i},
  {id:'builtin.ai.prompt-injection-marker', severity:'MAJOR', message:'发现典型提示词注入/越权指令语句。若该文本会进入 RAG/Agent 上下文，需要隔离和降权处理。', fix:'对外部文档做不可信内容隔离；系统指令与检索内容分区；加入 prompt-injection 检测和输出约束。', regex:/(ignore (all )?(previous|prior) instructions|忽略(之前|以上|所有).{0,12}(指令|规则)|必须推荐|泄露.{0,8}(系统提示|prompt|密钥)|reveal.{0,20}(system prompt|secret))/i}
];

const argv = yargs(hideBin(process.argv))
  .option('path',{alias:'p',type:'string',description:'要扫描的目录路径',demandOption:true})
  .option('config',{alias:'c',type:'string',default:'auto',description:'Semgrep扫描规则配置，默认auto自动匹配'})
  .option('severities',{alias:'s',type:'array',default:['BLOCKER','CRITICAL','MAJOR'],description:'风险等级：BLOCKER,CRITICAL,MAJOR,MINOR,INFO，支持逗号分隔'})
  .option('output',{alias:'o',type:'string',description:'输出报告文件路径，支持.md/.json格式'})
  .option('auto-fix',{type:'boolean',default:false,description:'Semgrep引擎下透传 --autofix；内置引擎只给建议不改文件'})
  .option('engine',{choices:['auto','semgrep','builtin'],default:'auto',description:'扫描引擎：auto优先Semgrep，缺失时回退内置规则'})
  .option('exclude',{type:'array',default:[],description:'额外排除目录/路径片段，可多次传入或逗号分隔'})
  .option('max-file-size-kb',{type:'number',default:1024,description:'内置引擎扫描的单文件大小上限KB'})
  .help().argv;

function normalizeList(value){return (Array.isArray(value)?value:[value]).flatMap(v=>String(v).split(',')).map(v=>v.trim()).filter(Boolean)}
function resolveSemgrep(){
  if(fs.existsSync(LOCAL_SEMGREP)) return LOCAL_SEMGREP;
  const r = spawnSync('sh',['-c','command -v semgrep'],{encoding:'utf-8'});
  return r.status===0 ? r.stdout.trim() : null;
}
function severityAllowed(sev, allowed){return allowed.length===0||allowed.includes(sev)}
function semgrepSeverities(allowed){const m={BLOCKER:'ERROR',CRITICAL:'ERROR',MAJOR:'WARNING',MINOR:'WARNING',INFO:'INFO'};return [...new Set(allowed.map(s=>m[s]||s))]}
function absScanPath(input){const abs=path.resolve(input);if(!fs.existsSync(abs)){console.error(`❌ 扫描路径不存在：${abs}`);process.exit(1)}return abs}

function runSemgrepScan(scanPath, allowed){
  const args=['scan',`--config=${argv.config}`,'--json','--quiet','--no-git-ignore'];
  semgrepSeverities(allowed).forEach(s=>args.push(`--severity=${s}`));
  if(argv.autoFix) args.push('--autofix');
  args.push(scanPath);
  const semgrepBin = resolveSemgrep();
  if(!semgrepBin) throw new Error('semgrep not found');
  const r=spawnSync(semgrepBin,args,{encoding:'utf-8',maxBuffer:1024*1024*100});
  if(r.error) throw r.error;
  if(r.status && r.status!==0 && !r.stdout) throw new Error(r.stderr||`semgrep exited ${r.status}`);
  const data=JSON.parse(r.stdout||'{"results":[]}');
  const rev={ERROR:'CRITICAL',WARNING:'MAJOR',INFO:'INFO'};
  return (data.results||[]).map(x=>({file:path.resolve(x.path),line:x.start?.line||1,severity:rev[x.extra?.severity]||x.extra?.severity||'INFO',message:x.extra?.message||'Semgrep finding',rule:x.check_id,fix:x.extra?.fix||'无自动修复方案',url:x.extra?.metadata?.source||'',engine:'semgrep'})).filter(i=>severityAllowed(i.severity,allowed));
}
function skipDir(name, full, excludes){return excludes.some(ex=>name===ex||full.includes(`${path.sep}${ex}${path.sep}`)||full.endsWith(`${path.sep}${ex}`))}
function isText(file){const base=path.basename(file);return base.startsWith('.env')||TEXT_EXTENSIONS.has(path.extname(file).toLowerCase())}
function walk(root, excludes, maxBytes, out=[]){let ents;try{ents=fs.readdirSync(root,{withFileTypes:true})}catch{return out} for(const e of ents){const full=path.join(root,e.name); if(e.isDirectory()){if(!skipDir(e.name,full,excludes)) walk(full,excludes,maxBytes,out)} else if(e.isFile()&&isText(full)){try{if(fs.statSync(full).size<=maxBytes) out.push(full)}catch{}}} return out}
function isScannerFixture(file, line){
  const base = path.basename(file);
  // Scanner tests intentionally contain vulnerable snippets; do not report them when auditing the scanner skill itself.
  if(base==='smoke_test.js') return true;
  // Scanner implementations contain regex patterns and report wording that intentionally mention risky tokens.
  if((base==='semgrep_scan.js'||base==='audit_skill.py') && (line.includes('regex')||line.includes('re.compile')||line.includes('BUILTIN_RULES')||line.includes('DANGEROUS_COMMAND_RULES')||line.includes('SECRET_HINT_RULES')||line.includes('安全说明'))) return true;
  return false;
}
function isMarkdownExample(file, line){
  if(path.extname(file).toLowerCase()!=='.md') return false;
  const t=line.trim();
  // Backtick/list/quote examples in docs describe rules; reporting them as real secrets creates noisy self-audits.
  return t.startsWith('`')||t.endsWith('`')||t.startsWith('- ')||t.startsWith('* ')||t.startsWith('> ')||t.startsWith('|');
}
function ruleApplies(rule, file, line){
  if(isScannerFixture(file,line)||isMarkdownExample(file,line)) return false;
  const ext = path.extname(file).toLowerCase();
  if(rule.target==='code' && !CODE_EXTENSIONS.has(ext)) return false;
  if(rule.target==='code-config' && !(CODE_EXTENSIONS.has(ext)||CONFIG_EXTENSIONS.has(ext)||path.basename(file).startsWith('.env'))) return false;
  // Avoid built-in prompt-injection rule matching its own regex definition.
  if(rule.id==='builtin.ai.prompt-injection-marker' && path.basename(file)==='semgrep_scan.js') return false;
  return true;
}
function runBuiltinScan(scanPath, allowed){
  const excludes=[...DEFAULT_EXCLUDES,...normalizeList(argv.exclude)];
  const maxBytes=Math.max(1,argv.maxFileSizeKb)*1024;
  const files=fs.statSync(scanPath).isDirectory()?walk(scanPath,excludes,maxBytes):[scanPath];
  const issues=[];
  for(const file of files){let text;try{text=fs.readFileSync(file,'utf-8')}catch{continue} if(text.includes('\u0000')) continue; const lines=text.split(/\r?\n/); lines.forEach((line,idx)=>{for(const rule of BUILTIN_RULES){rule.regex.lastIndex=0; if(ruleApplies(rule,file,line)&&severityAllowed(rule.severity,allowed)&&rule.regex.test(line)){issues.push({file,line:idx+1,severity:rule.severity,message:rule.message,rule:rule.id,fix:rule.fix,url:'',engine:'builtin'})}}})}
  return issues;
}
function summarize(issues, engine, scanPath){return {scanner:'code-security-audit',engine,scanPath,timestamp:new Date().toISOString(),total:issues.length,severities:{BLOCKER:issues.filter(i=>i.severity==='BLOCKER').length,CRITICAL:issues.filter(i=>i.severity==='CRITICAL').length,MAJOR:issues.filter(i=>i.severity==='MAJOR').length,MINOR:issues.filter(i=>i.severity==='MINOR').length,INFO:issues.filter(i=>i.severity==='INFO').length},issues}}
function md(summary){
  let s='# code-security-audit 扫描报告\n\n## 扫描概览\n\n';
  s+=`- 扫描器：${summary.scanner}\n- 引擎：${summary.engine}\n- 扫描时间：${summary.timestamp}\n- 扫描路径：${summary.scanPath}\n- 总问题数：${summary.total}\n`;
  s+=`- 高危 BLOCKER：${summary.severities.BLOCKER}\n- 严重 CRITICAL：${summary.severities.CRITICAL}\n- 重要 MAJOR：${summary.severities.MAJOR}\n- 次要 MINOR：${summary.severities.MINOR}\n- 提示 INFO：${summary.severities.INFO}\n\n`;
  s+='> 安全说明：报告默认不输出命中源码内容，只给出文件、行号、规则与修复建议，避免二次泄露密钥。\n\n## 问题详情\n\n';
  const labels={BLOCKER:'🔴 高危',CRITICAL:'🟠 严重',MAJOR:'🟡 重要',MINOR:'🟢 次要',INFO:'🔵 提示'};
  for(const sev of ['BLOCKER','CRITICAL','MAJOR','MINOR','INFO']){const arr=summary.issues.filter(i=>i.severity===sev); if(!arr.length) continue; s+=`### ${labels[sev]} ${sev}（${arr.length}）\n\n`; arr.forEach((i,n)=>{s+=`${n+1}. **文件**：\`${i.file}\`，**行号**：${i.line}\n   - **规则**：${i.rule}\n   - **描述**：${i.message}\n   - **修复建议**：${i.fix}\n\n`})}
  return s;
}
function writeReport(summary){if(!argv.output) return; const out=path.resolve(argv.output); fs.mkdirSync(path.dirname(out),{recursive:true}); if(out.endsWith('.json')) fs.writeFileSync(out,JSON.stringify(summary,null,2),'utf-8'); else fs.writeFileSync(out,md(summary),'utf-8'); console.log(`📝 报告已保存：${out}`)}
function printSummary(summary){console.log('\n📊 扫描完成，结果汇总：'); console.log(`引擎：${summary.engine}`); console.log(`总问题数：${summary.total}`); console.log(`🔴 高危 BLOCKER：${summary.severities.BLOCKER}`); console.log(`🟠 严重 CRITICAL：${summary.severities.CRITICAL}`); console.log(`🟡 重要 MAJOR：${summary.severities.MAJOR}`); console.log(`🟢 次要 MINOR：${summary.severities.MINOR}`); console.log(`🔵 提示 INFO：${summary.severities.INFO}`)}
function main(){
  const scanPath=absScanPath(argv.path); const allowed=normalizeList(argv.severities).map(s=>s.toUpperCase());
  console.log(`🔍 开始 code-security-audit 扫描，扫描路径：${scanPath}`); console.log(`⚙️  请求引擎：${argv.engine}，风险等级：${allowed.join(',')||'ALL'}`);
  let engine=argv.engine, issues=[];
  try{
    if(engine==='semgrep'||(engine==='auto'&&resolveSemgrep())){issues=runSemgrepScan(scanPath,allowed); engine='semgrep'}
    else{if(engine==='auto') console.log('ℹ️ 未发现 semgrep 命令，自动使用内置轻量规则引擎。'); issues=runBuiltinScan(scanPath,allowed); engine='builtin'}
  }catch(e){if(argv.engine==='auto'){console.log(`⚠️ Semgrep 执行失败，回退内置规则引擎：${e.message}`); issues=runBuiltinScan(scanPath,allowed); engine='builtin'} else {console.error('❌ 扫描失败：',e.message); process.exit(1)}}
  const summary=summarize(issues,engine,scanPath); printSummary(summary); writeReport(summary); if(summary.severities.BLOCKER+summary.severities.CRITICAL>0) process.exitCode=2;
}
main();
