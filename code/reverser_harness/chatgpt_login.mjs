import { randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync, chmodSync } from 'node:fs';
import { join } from 'node:path';
import { openaiProvider } from '@earendil-works/pi-ai/providers/openai';

const agentDir = process.env.PI_CODING_AGENT_DIR;
if (!agentDir) throw new Error('PI_CODING_AGENT_DIR is required');
mkdirSync(agentDir, { recursive: true, mode: 0o700 });
const hostIdFile = join(agentDir, 'chatgpt-host-id');
if (!existsSync(hostIdFile)) {
  try { writeFileSync(hostIdFile, randomUUID(), { encoding: 'utf8', mode: 0o600, flag: 'wx' }); }
  catch (error) { if (error.code !== 'EEXIST') throw error; }
}
const hostId = readFileSync(hostIdFile, 'utf8').trim();
const emit = value => process.stdout.write(JSON.stringify(value) + '\n');
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 5 * 60_000);

try {
  const credential = await openaiProvider().auth.oauth.login({
    signal: controller.signal,
    prompt: request => new Promise((_, reject) => {
      if (request.signal.aborted) return reject(new Error('로그인이 취소되었습니다.'));
      request.signal.addEventListener('abort', () => reject(new Error('로그인이 취소되었습니다.')), { once: true });
    }),
    notify: event => { if (event.type === 'auth_url') emit({ type: 'auth_url', url: event.url }); },
  }, { getDeviceId: () => hostId, agentName: 'Reverser' });

  const authFile = join(agentDir, 'auth.json');
  const auth = existsSync(authFile) ? JSON.parse(readFileSync(authFile, 'utf8')) : {};
  auth.openai = credential;
  const temporary = join(agentDir, `auth.${randomUUID()}.tmp`);
  writeFileSync(temporary, JSON.stringify(auth, null, 2), { encoding: 'utf8', mode: 0o600 });
  renameSync(temporary, authFile);
  chmodSync(authFile, 0o600);
  emit({ type: 'success' });
} catch (error) {
  emit({ type: 'error', message: error instanceof Error ? error.message.slice(0, 240) : '로그인에 실패했습니다.' });
  process.exitCode = 1;
} finally {
  clearTimeout(timer);
}
