import {
  CONSUMER_PAGE_DESCRIPTION,
  CONSUMER_PAGE_TITLE,
  START_CASE_CTA,
} from '@/lib/consumer-copy';

export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  agentName?: string;
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Caseflow',
  pageTitle: CONSUMER_PAGE_TITLE,
  pageDescription: CONSUMER_PAGE_DESCRIPTION,

  supportsChatInput: true,
  supportsVideoInput: true,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,

  logo: '/caseflow-mark.svg',
  accent: '#0a0a0a',
  logoDark: '/caseflow-mark.svg',
  accentDark: '#0a0a0a',
  startButtonText: START_CASE_CTA,

  agentName: process.env.AGENT_NAME ?? 'caseflow-agent',
  sandboxId: undefined,
};
