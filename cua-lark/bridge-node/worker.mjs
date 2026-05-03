/**
 * CUA-Lark Bridge: stdin JSON lines -> GUIAgent (singleton), stdout JSONL only.
 * 通过 UI_TARS_DESKTOP_ROOT 从 monorepo 内 dist 动态 import（不依赖 bridge-node 本地 node_modules）。
 */
import path from 'node:path';
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';

const root = process.env.UI_TARS_DESKTOP_ROOT;
if (!root) {
  process.stderr.write('[bridge] FATAL: UI_TARS_DESKTOP_ROOT is not set\n');
  process.exit(1);
}

const sdkUrl = pathToFileURL(
  path.join(root, 'packages/ui-tars/sdk/dist/index.mjs'),
).href;
const nutUrl = pathToFileURL(
  path.join(root, 'packages/ui-tars/operators/nut-js/dist/index.mjs'),
).href;

const { GUIAgent, StatusEnum } = await import(sdkUrl);
const { NutJSOperator } = await import(nutUrl);

const stderrLog = (level, ...args) => {
  const line = `[bridge:${level}] ${args.map((a) => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')}\n`;
  process.stderr.write(line);
};

const logger = {
  log: (...a) => stderrLog('log', ...a),
  info: (...a) => stderrLog('info', ...a),
  warn: (...a) => stderrLog('warn', ...a),
  error: (...a) => stderrLog('error', ...a),
};

function emit(obj) {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

function pickLastScreenshot(data) {
  const convs = data.conversations || [];
  for (let i = convs.length - 1; i >= 0; i -= 1) {
    const b64 = convs[i].screenshotBase64;
    if (b64) return b64;
  }
  return null;
}

const operator = new NutJSOperator();

const runCtx = {
  lastStatus: StatusEnum.INIT,
  lastShot: null,
};

let guiAgent;

function getAgent() {
  if (guiAgent) return guiAgent;
  const baseURL = process.env.VLM_BASE_URL || '';
  const apiKey = process.env.VLM_API_KEY || '';
  const model = process.env.VLM_MODEL || '';
  const useResponsesApi = process.env.VLM_USE_RESPONSES_API === '1';

  if (!baseURL || !apiKey || !model) {
    throw new Error('Missing VLM_BASE_URL, VLM_API_KEY or VLM_MODEL in environment');
  }

  guiAgent = new GUIAgent({
    model: {
      baseURL,
      apiKey,
      model,
      useResponsesApi,
    },
    operator,
    logger,
    maxLoopCount: 40,
    onData: ({ data }) => {
      runCtx.lastStatus = data.status;
      const shot = pickLastScreenshot(data);
      if (shot) runCtx.lastShot = shot;
      emit({
        type: 'step',
        status: data.status,
        hasScreenshot: Boolean(shot),
        instruction: data.instruction,
        modelName: data.modelName,
      });
    },
    onError: ({ data, error }) => {
      emit({
        type: 'error',
        status: data?.status,
        message: error?.message || String(error),
      });
    },
  });
  return guiAgent;
}

let processing = Promise.resolve();

function enqueue(fn) {
  processing = processing.then(fn).catch((e) => {
    emit({ type: 'done', ok: false, error: String(e), op: 'unknown' });
  });
  return processing;
}

async function handleRun(req) {
  const agent = getAgent();
  const instruction = req.instruction;
  if (!instruction || typeof instruction !== 'string') {
    emit({ type: 'done', ok: false, op: 'run', error: 'missing instruction' });
    return;
  }
  const maxLoop = Number(req.maxLoopCount ?? req.max_loop_count ?? 20);
  agent.config.maxLoopCount = Number.isFinite(maxLoop) ? maxLoop : 20;

  runCtx.lastStatus = StatusEnum.INIT;
  runCtx.lastShot = null;

  await agent.run(instruction);

  const ok = runCtx.lastStatus === StatusEnum.END;

  emit({
    type: 'done',
    op: 'run',
    ok,
    status: runCtx.lastStatus,
    last_screenshot_base64: runCtx.lastShot,
  });
}

async function handlePause() {
  getAgent().pause();
  emit({ type: 'done', op: 'pause', ok: true });
}

async function handleResume() {
  getAgent().resume();
  emit({ type: 'done', op: 'resume', ok: true });
}

async function handleStop() {
  getAgent().stop();
  emit({ type: 'done', op: 'stop', ok: true });
}

async function handleShutdown() {
  emit({ type: 'done', op: 'shutdown', ok: true });
  process.exit(0);
}

async function handleLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return;
  let req;
  try {
    req = JSON.parse(trimmed);
  } catch (e) {
    emit({ type: 'done', ok: false, op: 'parse', error: `invalid json: ${e}` });
    return;
  }
  const op = req.op;
  switch (op) {
    case 'run':
      await handleRun(req);
      break;
    case 'pause':
      await handlePause();
      break;
    case 'resume':
      await handleResume();
      break;
    case 'stop':
      await handleStop();
      break;
    case 'shutdown':
      await handleShutdown();
      break;
    default:
      emit({ type: 'done', ok: false, op: String(op), error: 'unknown op' });
  }
}

const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on('line', (line) => {
  enqueue(() => handleLine(line));
});
rl.on('close', () => {
  enqueue(async () => {
    emit({ type: 'done', op: 'shutdown', ok: true, reason: 'stdin_closed' });
    process.exit(0);
  });
});
