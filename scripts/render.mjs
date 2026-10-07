#!/usr/bin/env node
import { spawnSync } from 'child_process';
import { existsSync, mkdirSync, copyFileSync } from 'fs';
import path from 'path';

// 1. Resolve Chrome executable path
let browserPath = process.env.HYPERFRAMES_BROWSER_PATH;
if (!browserPath) {
  const candidates = [
    'C:\\Users\\gerap\\.cache\\hyperframes\\chrome-wrapper.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
  ];
  for (const c of candidates) {
    if (existsSync(c)) {
      browserPath = c;
      break;
    }
  }
}

// 2. Setup environment
const env = { ...process.env };
if (browserPath) {
  env.HYPERFRAMES_BROWSER_PATH = browserPath;
}

if (process.platform === 'win32' && existsSync('D:\\temp')) {
  env.TEMP = 'D:\\temp';
  env.TMP = 'D:\\temp';
}

// 3. Forward args or default to safe temp output copied back to renders/
const args = process.argv.slice(2);
const hasOutput = args.includes('-o') || args.includes('--output');

let tempOutput = null;
if (!hasOutput && existsSync('D:\\temp')) {
  tempOutput = 'D:\\temp\\demo-video.mp4';
  args.push('-o', tempOutput);
}

const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const res = spawnSync(npxCmd, ['--yes', 'hyperframes@0.8.140', 'render', ...args], {
  stdio: 'inherit',
  env,
  shell: true
});

if (res.status === 0 && tempOutput && existsSync(tempOutput)) {
  const destDir = path.resolve('renders');
  if (!existsSync(destDir)) mkdirSync(destDir, { recursive: true });
  copyFileSync(tempOutput, path.join(destDir, 'demo-video.mp4'));
  console.log(`✓ Copied final video to renders/demo-video.mp4`);
}

process.exit(res.status ?? 0);
