#!/usr/bin/env node
/** Backward-compatible wrapper documented by SKILL.md/README.md. */
const { spawnSync } = require('child_process');
const args = process.argv.slice(2);
const r = spawnSync(process.execPath, [require.resolve('./analyze.js'), '--action=quality-gate', ...args], { stdio: 'inherit' });
process.exit(r.status ?? 1);
