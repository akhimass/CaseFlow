import { type GatewayMetadata, gatewayChat } from '@/lib/gateway';

export type ReasonResponse = {
  content: string;
  model: string;
  provider: string;
  latencyMs: number;
};

export async function reason(
  prompt: string,
  context: string,
  metadata?: GatewayMetadata
): Promise<ReasonResponse> {
  const result = await gatewayChat(
    'qwen-max',
    [
      { role: 'system', content: 'You are a PI intake reasoning assistant. Reply concisely.' },
      { role: 'user', content: context ? `${prompt}\n\nContext:\n${context}` : prompt },
    ],
    { temperature: 0.2, metadata }
  );
  return {
    content: result.content,
    model: result.model,
    provider: result.provider,
    latencyMs: result.latencyMs,
  };
}
