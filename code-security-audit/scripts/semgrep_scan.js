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
const SEVERITY_ORDER = {INFO:0, MINOR:1, MAJOR:2, CRITICAL:3, BLOCKER:4};

const BUILTIN_RULES = [
  {id:'builtin.secrets.generic-assignment', target:'code-config', severity:'CRITICAL', message:'疑似敏感凭据硬编码。请改用环境变量、密钥管理系统或 OpenClaw 安全配置，并立即轮换已暴露凭据。', fix:'删除硬编码密钥，改为 process.env/配置中心/Secret Manager；提交前确认历史记录中没有残留。', regex:/\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|private[_-]?key|client[_-]?secret)\b\s*[:=]\s*['"]?[^'"\s]{8,}/i},
  {id:'builtin.secrets.private-key', target:'all', severity:'BLOCKER', message:'发现私钥块标记。私钥不应出现在代码仓库或普通配置目录中。', fix:'移除私钥文件，放入受控密钥存储；若已提交或同步过，立即轮换密钥。', regex:/-----BEGIN (RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----/},
  {id:'builtin.crypto.md5-sha1', target:'code', severity:'MAJOR', message:'发现 MD5/SHA1 等弱哈希算法。用于安全场景时存在碰撞风险。', fix:'密码存储使用 Argon2/bcrypt/scrypt；完整性校验至少使用 SHA-256/HMAC-SHA256。', regex:/\b(md5|sha1)\s*\(|createHash\(\s*['"](?:md5|sha1)['"]\s*\)|hashlib\.(?:md5|sha1)\s*\(/i},
  {id:'builtin.command-injection.shell-exec', target:'code', severity:'CRITICAL', message:'发现 shell 命令执行入口。若拼接了外部输入，可能导致命令注入。', fix:'优先使用 execFile/spawn 参数数组；校验/白名单化输入；避免 shell:true 和字符串拼接。', regex:/\b(execSync|exec|popen|system|subprocess\.Popen|os\.system|shell_exec|passthru)\s*\(/i},
  {id:'builtin.code-injection.eval', target:'code', severity:'CRITICAL', message:'发现 eval/new Function 等动态代码执行，若输入可控可能导致代码注入。', fix:'移除动态执行；使用白名单映射、表达式解析器或安全沙箱。', regex:/\b(eval|Function|setTimeout|setInterval)\s*\(/i},
  {id:'builtin.sql.string-concat', target:'code', severity:'MAJOR', message:'疑似 SQL 字符串拼接。若包含外部输入，可能导致 SQL 注入。', fix:'使用参数化查询/预编译语句；禁止直接拼接 req/query/body/params。', regex:/(SELECT|INSERT|UPDATE|DELETE)\b[^\n]*(\+|\$\{|%s|format\()/i},
  {id:'builtin.tls.disabled-verify', target:'code-config', severity:'MAJOR', message:'发现关闭 TLS/证书校验配置。可能遭受中间人攻击。', fix:'启用证书校验；如需自签证书，配置可信 CA，不要关闭校验。', regex:/(verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['"]0['"])/i},
  {id:'builtin.ai.prompt-injection-marker', target:'all', severity:'MAJOR', message:'发现典型 Prompt Injection / RAG 污染标记。若该内容会进入 LLM 上下文，应隔离为不可信数据。', fix:'对外部文档做来源标注、上下文隔离和指令降权；不要让检索内容覆盖系统/开发者指令。', regex:/(ignore previous instructions|reveal (the )?system prompt|developer message|BEGIN SYSTEM PROMPT|你现在是|忽略之前的指令)/i},
  {id:'builtin.auth.jwt-none', target:'code-config', severity:'CRITICAL', message:'JWT 配置疑似允许 none 算法或未限制算法，可能导致令牌伪造。', fix:'显式限定强算法如 RS256/HS256；拒绝 alg=none；校验 issuer/audience/过期时间。', regex:/(algorithms?\s*[:=]\s*\[[^\]]*['"]none['"]|alg\s*[:=]\s*['"]none['"])/i},
  {id:'builtin.auth.hardcoded-jwt-secret', target:'code-config', severity:'CRITICAL', message:'疑似硬编码 JWT/Session Secret。泄露后可伪造会话或令牌。', fix:'使用高熵环境变量或密钥管理服务，轮换已泄露 secret，并设置合理过期时间。', regex:/(jwt[_-]?secret|session[_-]?secret|SECRET_KEY)\s*[:=]\s*['"][^'"]{8,}['"]/i},
  {id:'builtin.nosql.operator-injection', target:'code', severity:'MAJOR', message:'疑似 NoSQL 操作符注入风险：用户输入可能直接进入 Mongo 查询条件。', fix:'对查询参数做类型校验和字段白名单；拒绝对象型操作符如 $ne/$gt/$regex；使用 schema validator。', regex:/(find(?:One)?|update(?:One|Many)?|delete(?:One|Many)?)\s*\(\s*\{[^}]*req\.(?:body|query|params)|\$where\s*:/i},
  {id:'builtin.prototype-pollution.merge', target:'code', severity:'MAJOR', message:'疑似原型污染风险：深度合并/对象赋值可能处理不可信输入。', fix:'过滤 __proto__/constructor/prototype；使用安全 merge 库版本；对输入 schema 做白名单校验。', regex:/(Object\.assign\s*\([^)]*req\.(?:body|query)|(?:merge|defaultsDeep|extend)\s*\([^)]*req\.(?:body|query))/i},
  {id:'builtin.path-traversal.file-read', target:'code', severity:'MAJOR', message:'疑似路径遍历：文件读写 API 可能接收用户可控路径。', fix:'使用固定根目录、path.resolve 后校验前缀；拒绝 ../、绝对路径和符号链接逃逸。', regex:/(readFile|readFileSync|createReadStream|sendFile|open\s*\(|FileInputStream|Files\.read).*req\.(?:query|params|body)/i},
  {id:'builtin.xxe.xml-parser', target:'code', severity:'MAJOR', message:'发现 XML 解析入口，请确认已禁用外部实体和 DTD。', fix:'禁用 DTD/external entity；使用安全 XML 解析配置；避免解析不可信 XML。', regex:/(DocumentBuilderFactory|SAXParserFactory|XMLInputFactory|lxml\.etree|xml2js|libxmljs)/i},
  {id:'builtin.config.debug-enabled', target:'code-config', severity:'MAJOR', message:'疑似生产调试模式开启，可能导致敏感信息泄露或调试接口暴露。', fix:'生产环境关闭 DEBUG/dev mode；通过环境区分配置并加入部署前检查。', regex:/(DEBUG\s*=\s*True|debug\s*[:=]\s*true|NODE_ENV\s*[:=]\s*['"]development['"])/i},
  {id:'builtin.config.cors-wildcard', target:'code-config', severity:'MAJOR', message:'CORS 疑似允许任意来源，可能扩大跨站数据访问风险。', fix:'限定可信 Origin；涉及凭据时禁止 *；按环境维护 Origin 白名单。', regex:/(cors\s*\([^)]*origin\s*[:=]\s*['"]\*['"]|Access-Control-Allow-Origin['"]?\s*[:=]\s*['"]\*)/i},
  {id:'builtin.container.privileged-root', target:'code-config', severity:'MAJOR', message:'容器配置疑似使用特权模式或 root 运行。', fix:'禁用 privileged；设置非 root USER；开启只读文件系统和最小 Linux capabilities。', regex:/(privileged\s*:\s*true|USER\s+root|user\s*:\s*['"]?0['"]?)/i},
];

const argv = yargs(hideBin(process.argv))
  .option('engine', { type:'string', default:'auto', choices:['auto','semgrep','builtin'] })
  .option('path', { type:'string', demandOption:true })
  .option('config', { type:'string', default:'auto' })
  .option('severities', { type:'string', default:'BLOCKER,CRITICAL,MAJOR,MINOR,INFO' })
  .option('output', { type:'string' })
  .option('exclude', { type:'array', default:[] })
  .option('auto-fix', { type:'boolean', default:false })
  .option('mode', { type:'string', default:'standard', choices:['quick','standard','deep'], describe:'Audit depth hint used by builtin dependency/config checks' })
  .option('fail-on', { type:'string', default:'CRITICAL', describe:'Minimum severity that returns exit code 2: BLOCKER,CRITICAL,MAJOR,MINOR,INFO' })
  .option('max-file-size-kb', { type:'number', default:1024 })
  .help().argv;

function splitCsv(values) {
  const out = [];
  for (const value of values || []) String(value).split(',').map(s => s.trim()).filter(Boolean).forEach(v => out.push(v));
  return out;
}
function semgrepBin() {
  if (fs.existsSync(LOCAL_SEMGREP)) return LOCAL_SEMGREP;
  const found = spawnSync('which', ['semgrep'], {encoding:'utf-8'});
  return found.status === 0 ? found.stdout.trim() : null;
}
function walk(dir, files=[]) {
  for (const ent of fs.readdirSync(dir, {withFileTypes:true})) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p, files);
    else if (ent.isFile()) files.push(p);
  }
  return files;
}
function shouldIncludeFile(file, excludes, maxBytes) {
  const relParts = file.split(path.sep);
  if (relParts.some(p => excludes.has(p))) return false;
  if (!TEXT_EXTENSIONS.has(path.extname(file)) && !['Dockerfile','Makefile'].includes(path.basename(file))) return false;
  try { return fs.statSync(file).size <= maxBytes; } catch { return false; }
}
function detectLanguage(root) {
  const present = (name) => fs.existsSync(path.join(root, name));
  const langs = [];
  if (present('package.json') || present('package-lock.json') || present('pnpm-lock.yaml') || present('yarn.lock')) langs.push('node');
  if (present('requirements.txt') || present('pyproject.toml') || present('Pipfile') || present('poetry.lock')) langs.push('python');
  if (present('go.mod')) langs.push('go');
  if (present('pom.xml') || present('build.gradle') || present('build.gradle.kts')) langs.push('java');
  return langs;
}
function addManifestFindings(root, files, findings) {
  const rels = new Set(files.map(f => path.relative(root, f)));
  const langs = detectLanguage(root);
  if (langs.length === 0) findings.push({file:'.', line:1, id:'builtin.project.unknown-stack', severity:'INFO', message:'未识别到常见依赖清单。深度依赖审计可能受限。', fix:'确认项目根目录是否正确；为对应语言提交 lockfile/manifest。'});
  for (const lang of langs) {
    if (lang === 'node' && !rels.has('package-lock.json') && !rels.has('pnpm-lock.yaml') && !rels.has('yarn.lock')) findings.push({file:'package.json', line:1, id:'builtin.supply-chain.node-missing-lockfile', severity:'MAJOR', message:'Node 项目缺少 lockfile，依赖版本不可复现，供应链风险升高。', fix:'提交 package-lock.json/pnpm-lock.yaml/yarn.lock，并在 CI 中使用 npm ci/pnpm --frozen-lockfile。'});
    if (lang === 'python' && rels.has('requirements.txt')) {
      try {
        fs.readFileSync(path.join(root, 'requirements.txt'), 'utf8').split(/\r?\n/).forEach((line, idx) => {
          const t = line.trim();
          if (t && !t.startsWith('#') && !/[=<>!~]=|@/.test(t)) findings.push({file:'requirements.txt', line:idx+1, id:'builtin.supply-chain.python-unpinned', severity:'MINOR', message:'Python 依赖未固定版本，构建可复现性和供应链审计能力下降。', fix:'固定版本或使用带 hash 的锁文件，例如 pip-tools/poetry lock。'});
        });
      } catch {}
    }
  }
}
function builtinScan(root) {
  const excludes = new Set([...DEFAULT_EXCLUDES, ...splitCsv(argv.exclude)]);
  const maxBytes = Number(argv.maxFileSizeKb || 1024) * 1024;
  const sevAllow = new Set(String(argv.severities).split(',').map(s => s.trim().toUpperCase()).filter(Boolean));
  const files = walk(root).filter(f => shouldIncludeFile(f, excludes, maxBytes));
  const findings = [];
  addManifestFindings(root, files, findings);
  for (const file of files) {
    const ext = path.extname(file);
    const rel = path.relative(root, file);
    const isCode = CODE_EXTENSIONS.has(ext);
    const isConfig = CONFIG_EXTENSIONS.has(ext) || ['Dockerfile','Makefile'].includes(path.basename(file));
    const text = fs.readFileSync(file, 'utf-8');
    const lines = text.split(/\r?\n/);
    for (const rule of BUILTIN_RULES) {
      if (rule.target === 'code' && !isCode) continue;
      if (rule.target === 'config' && !isConfig) continue;
      if (rule.target === 'code-config' && !isCode && !isConfig) continue;
      if (!sevAllow.has(rule.severity)) continue;
      for (let i=0;i<lines.length;i++) if (rule.regex.test(lines[i])) findings.push({file:rel,line:i+1,id:rule.id,severity:rule.severity,message:rule.message,fix:rule.fix});
    }
  }
  return findings.filter(f => sevAllow.has(String(f.severity).toUpperCase()));
}
function runSemgrep(root) {
  const bin = semgrepBin();
  if (!bin) throw new Error('Semgrep not found');
  const args = ['scan','--json'];
  if (argv.config && argv.config !== 'auto') args.push('--config', argv.config); else args.push('--config', 'auto');
  for (const ex of splitCsv(argv.exclude)) args.push('--exclude', ex);
  if (argv.autoFix) args.push('--autofix');
  args.push(root);
  const r = spawnSync(bin, args, {encoding:'utf-8', maxBuffer: 64*1024*1024});
  if (r.status !== 0 && !r.stdout) throw new Error(r.stderr || 'semgrep failed');
  const data = JSON.parse(r.stdout || '{}');
  return (data.results || []).map(x => ({file: path.relative(root, x.path || ''), line: x.start?.line || 1, id: x.check_id || 'semgrep', severity: mapSemgrepSeverity(x.extra?.severity), message: x.extra?.message || x.check_id || 'Semgrep finding', fix: x.extra?.fix || x.extra?.metadata?.fix || '参考规则说明修复，并验证 Source → Sink 数据流。'}));
}
function mapSemgrepSeverity(sev) {
  const s = String(sev || '').toUpperCase();
  if (s === 'ERROR') return 'CRITICAL';
  if (s === 'WARNING') return 'MAJOR';
  if (s === 'INFO') return 'INFO';
  return ['BLOCKER','CRITICAL','MAJOR','MINOR','INFO'].includes(s) ? s : 'MAJOR';
}
function summarize(findings, engine, root) {
  const severities = {BLOCKER:0,CRITICAL:0,MAJOR:0,MINOR:0,INFO:0};
  for (const f of findings) severities[f.severity] = (severities[f.severity] || 0) + 1;
  return {tool:'code-security-audit', engine, mode: argv.mode, scannedPath: root, generatedAt: new Date().toISOString(), total: findings.length, severities, findings};
}
function printSummary(report) { console.log(`code-security-audit ${report.engine} scan: ${report.total} findings`); console.log(JSON.stringify(report.severities)); }
function writeReport(report) {
  if (!argv.output) return;
  const out = path.resolve(argv.output);
  fs.mkdirSync(path.dirname(out), {recursive:true});
  if (out.endsWith('.json')) fs.writeFileSync(out, JSON.stringify(report, null, 2));
  else {
    const lines = ['# Code Security Audit Report', '', `- Engine: ${report.engine}`, `- Mode: ${report.mode}`, `- Path: ${report.scannedPath}`, `- Total: ${report.total}`, '', '## Findings'];
    for (const f of report.findings) lines.push(`\n### ${f.severity} ${f.id}\n- Location: ${f.file}:${f.line}\n- Description: ${f.message}\n- Fix: ${f.fix}`);
    fs.writeFileSync(out, lines.join('\n'));
  }
  console.log(`report: ${out}`);
}
function main() {
  const scanPath = path.resolve(argv.path);
  if (!fs.existsSync(scanPath)) { console.error(`path not found: ${scanPath}`); process.exit(1); }
  let engine = argv.engine;
  let issues;
  if (engine === 'semgrep') issues = runSemgrep(scanPath);
  else if (engine === 'builtin') issues = builtinScan(scanPath);
  else {
    try { issues = runSemgrep(scanPath); engine = 'semgrep'; }
    catch (e) { console.warn(`semgrep unavailable, fallback to builtin: ${e.message}`); issues = builtinScan(scanPath); engine = 'builtin'; }
  }
  const report = summarize(issues, engine, scanPath);
  printSummary(report);
  writeReport(report);
  const failOn = String(argv.failOn || 'CRITICAL').toUpperCase();
  const failThreshold = SEVERITY_ORDER[failOn] ?? SEVERITY_ORDER.CRITICAL;
  process.exitCode = Object.entries(report.severities).some(([sev, count]) => (SEVERITY_ORDER[sev] ?? -1) >= failThreshold && count > 0) ? 2 : 0;
}
main();
