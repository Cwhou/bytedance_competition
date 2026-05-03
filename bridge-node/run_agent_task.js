require('dotenv').config({ path: require('path').resolve(__dirname, '../.env') });

const { GUIAgent } = require('@ui-tars/sdk');
const { NutJSOperator } = require('@ui-tars/operator-nut-js');

const userInstruction = process.argv[2];
if (!userInstruction) {
  console.error(JSON.stringify({ type: 'error', message: '请传入指令参数' }));
  process.exit(1);
}

const MODEL_CONFIG = {
  baseURL: process.env.ARK_BASE_URL,
  apiKey: process.env.ARK_API_KEY,
  model: process.env.ARK_MODEL,
  // 可选：如果你的 Provider 支持 OpenAI Response API，可打开以改善长上下文
  // useResponsesApi: process.env.ARK_USE_RESPONSES_API === '1',
};

function validateModelConfig() {
  const missing = [];
  if (!MODEL_CONFIG.baseURL) missing.push('ARK_BASE_URL');
  if (!MODEL_CONFIG.apiKey) missing.push('ARK_API_KEY');
  if (!MODEL_CONFIG.model) missing.push('ARK_MODEL');
  if (missing.length) {
    console.error(
      JSON.stringify({
        type: 'error',
        message: `缺少环境变量：${missing.join(', ')}（请在 .env 中配置）`,
      }),
    );
    process.exit(1);
  }
}

async function executeTask() {
  validateModelConfig();

  try {
    const guiAgent = new GUIAgent({
      model: MODEL_CONFIG,
      operator: new NutJSOperator(),
      maxLoopCount: Number(process.env.UI_TARS_MAX_LOOP ?? 20),
      onData: ({ data }) => {
        process.stdout.write(JSON.stringify({ type: 'step', data }) + '\n');
      },
      onError: ({ error }) => {
        process.stdout.write(
          JSON.stringify({ type: 'error', message: error?.message || String(error) }) + '\n',
        );
      },
    });

    await guiAgent.run(userInstruction);
    process.stdout.write(
      JSON.stringify({ type: 'finish', message: '任务执行完成' }) + '\n',
    );
  } catch (err) {
    process.stdout.write(
      JSON.stringify({ type: 'error', message: err?.message || String(err) }) + '\n',
    );
    process.exit(1);
  }
}

executeTask();

