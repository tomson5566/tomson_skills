#!/usr/bin/env node
/** Backward-compatible wrapper documented by SKILL.md/README.md. */
const { spawnSync } = require('child_process');
const args = process.argv.slice(2);
const hasFormat = args.some(a => a.startsWith('--format='));
const finalArgs = hasFormat ? args : [...args, '--format=markdown'];
const r = spawnSync(process.execPath, [require.resolve('./analyze.js'), '--action=analyze', ...finalArgs], { stdio: 'inherit' });
process.exit(r.status ?? 1);
