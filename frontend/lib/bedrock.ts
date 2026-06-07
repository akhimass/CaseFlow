import {
  BedrockRuntimeClient,
  ConverseCommand,
  type Message,
} from '@aws-sdk/client-bedrock-runtime';

const region = () => process.env.AWS_REGION ?? process.env.AWS_DEFAULT_REGION ?? 'us-east-1';
const modelId = () => process.env.BEDROCK_FALLBACK_MODEL ?? 'us.amazon.nova-lite-v1:0';

export type OpenAiStyleMessage = {
  role: 'system' | 'user' | 'assistant';
  content: string;
};

function iamConfigured(): boolean {
  return Boolean(process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY);
}

function bearerConfigured(): boolean {
  return Boolean(process.env.AWS_BEARER_TOKEN_BEDROCK ?? process.env.AWS_BEDROCK_API_KEY);
}

export function bedrockConfigured(): boolean {
  return bearerConfigured() || iamConfigured();
}

function splitOpenAiMessages(messages: OpenAiStyleMessage[]): {
  system?: string;
  bedrockMessages: Message[];
} {
  const systemParts: string[] = [];
  const bedrockMessages: Message[] = [];

  for (const message of messages) {
    if (message.role === 'system') {
      if (message.content) systemParts.push(message.content);
      continue;
    }
    bedrockMessages.push({
      role: message.role,
      content: [{ text: message.content }],
    });
  }

  return {
    system: systemParts.length ? systemParts.join('\n\n') : undefined,
    bedrockMessages,
  };
}

async function bedrockConverseIam(
  messages: Message[],
  options?: { system?: string; temperature?: number; maxTokens?: number }
): Promise<{ content: string; model: string }> {
  const client = new BedrockRuntimeClient({
    region: region(),
    credentials: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
    },
  });

  const response = await client.send(
    new ConverseCommand({
      modelId: modelId(),
      messages,
      system: options?.system ? [{ text: options.system }] : undefined,
      inferenceConfig: {
        temperature: options?.temperature ?? 0.2,
        maxTokens: options?.maxTokens ?? 1024,
      },
    })
  );

  const content = response.output?.message?.content?.find((block) => block.text)?.text ?? '';
  if (!content) {
    throw new Error('Bedrock returned empty content');
  }

  return { content, model: modelId() };
}

async function bedrockConverseBearer(
  messages: Message[],
  options?: { system?: string; temperature?: number; maxTokens?: number }
): Promise<{ content: string; model: string }> {
  const apiKey = process.env.AWS_BEARER_TOKEN_BEDROCK ?? process.env.AWS_BEDROCK_API_KEY;
  if (!apiKey) {
    throw new Error('AWS_BEARER_TOKEN_BEDROCK is not configured');
  }

  const encodedModel = encodeURIComponent(modelId());
  const url = `https://bedrock-runtime.${region()}.amazonaws.com/model/${encodedModel}/converse`;

  const payload: Record<string, unknown> = {
    messages,
    inferenceConfig: {
      temperature: options?.temperature ?? 0.2,
      maxTokens: options?.maxTokens ?? 1024,
    },
  };
  if (options?.system) {
    payload.system = [{ text: options.system }];
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const detail = (await res.text()).slice(0, 500);
    throw new Error(`Bedrock error ${res.status}: ${detail}`);
  }

  const data = (await res.json()) as {
    output?: { message?: { content?: Array<{ text?: string }> } };
  };
  const content = data.output?.message?.content?.find((block) => block.text)?.text ?? '';
  if (!content) {
    throw new Error('Bedrock returned empty content');
  }

  return { content, model: modelId() };
}

export async function bedrockChat(
  messages: OpenAiStyleMessage[],
  options?: { temperature?: number; maxTokens?: number }
): Promise<{ content: string; model: string; provider: 'bedrock' }> {
  const { system, bedrockMessages } = splitOpenAiMessages(messages);
  if (!bedrockMessages.length) {
    throw new Error('Bedrock chat requires at least one user/assistant message');
  }

  const converseOptions = {
    system,
    temperature: options?.temperature,
    maxTokens: options?.maxTokens,
  };

  const result = bearerConfigured()
    ? await bedrockConverseBearer(bedrockMessages, converseOptions)
    : await bedrockConverseIam(bedrockMessages, converseOptions);

  return { ...result, provider: 'bedrock' };
}
