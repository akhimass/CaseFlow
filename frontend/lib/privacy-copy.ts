export function detectConsumerLanguage(): 'en' | 'es' {
  if (typeof navigator === 'undefined') return 'en';
  const lang = navigator.language?.toLowerCase() ?? 'en';
  return lang.startsWith('es') ? 'es' : 'en';
}

export const PRIVACY_COPY = {
  en: {
    title: 'Privacy policy',
    summary:
      'Caseflow records intake conversations to match you with a participating personal injury firm. We treat your information carefully and limit what firms and AI systems can see.',
    sections: [
      {
        heading: 'What we collect',
        body: 'During video intake we capture your voice, optional camera video, and any documents you show the camera. We also store case details you share (injury type, location, timeline) and technical session metadata.',
      },
      {
        heading: 'How we protect your data',
        body: 'Names, phone numbers, and street addresses are redacted before they reach firm dashboards or external AI models. Raw document images are stored in a separate encrypted bucket — they are never shown on the firm dashboard.',
      },
      {
        heading: 'Who can see your information',
        body: 'Matched participating firms receive a redacted case file and verbal brief. Caseflow is not a law firm and does not provide legal advice.',
      },
      {
        heading: 'Speech audio limitation',
        body: 'Live speech audio is not regex-redacted during the call (STT limitation). Production roadmap: on-device redaction before audio leaves your device.',
      },
      {
        heading: 'Retention',
        body: 'Session transcripts, parsed documents, and audit logs are retained to support your case match and firm handoff. You may request deletion by contacting the firm you are matched with.',
      },
    ],
    back: 'Back to consent',
    home: 'Back to home',
  },
  es: {
    title: 'Política de privacidad',
    summary:
      'Caseflow registra las conversaciones de intake para conectarle con un bufete participante. Tratamos su información con cuidado y limitamos lo que los bufetes y los sistemas de IA pueden ver.',
    sections: [
      {
        heading: 'Qué recopilamos',
        body: 'Durante la intake por video capturamos su voz, video opcional de la cámara y los documentos que muestre. También guardamos los detalles del caso que comparta (tipo de lesión, ubicación, cronología) y metadatos técnicos de la sesión.',
      },
      {
        heading: 'Cómo protegemos sus datos',
        body: 'Redactamos nombres, teléfonos y direcciones antes de que lleguen al panel del bufete o a modelos de IA externos. Las imágenes de documentos se guardan en un bucket cifrado aparte — nunca se muestran en el panel.',
      },
      {
        heading: 'Quién puede ver su información',
        body: 'Los bufetes participantes que coincidan reciben un expediente redactado y un resumen verbal. Caseflow no es un bufete y no ofrece asesoría legal.',
      },
      {
        heading: 'Limitación del audio en vivo',
        body: 'El audio en vivo no se redacta por regex durante la llamada (limitación de STT). Hoja de ruta: redacción en el dispositivo antes de que el audio salga de su teléfono.',
      },
      {
        heading: 'Retención',
        body: 'Las transcripciones, documentos analizados y registros de auditoría se conservan para apoyar la coincidencia con un bufete y la entrega del caso. Puede solicitar eliminación contactando al bufete con el que fue emparejado.',
      },
    ],
    back: 'Volver al consentimiento',
    home: 'Volver al inicio',
  },
} as const;

export const CONSENT_COPY = {
  en: {
    title: 'Before we begin',
    body: 'Caseflow records this intake to match you with a participating personal injury firm. We redact names, phone numbers, and addresses before they reach firm dashboards or external AI models. Raw document images are stored in a separate encrypted bucket — never shown on the firm dashboard.',
    checkbox:
      'I understand this intake will be recorded and processed under Caseflow’s privacy controls.',
    privacyLink: 'Read our privacy policy',
    start: 'Start intake',
    back: 'Back to home',
    sttNote:
      'Note: live speech audio is not regex-redacted during the call (STT limitation). Production roadmap: on-device redaction.',
  },
  es: {
    title: 'Antes de comenzar',
    body: 'Caseflow registra esta intake para conectarle con un bufete participante. Redactamos nombres, teléfonos y direcciones antes de que lleguen al panel del bufete o a modelos de IA externos. Las imágenes de documentos se guardan en un bucket cifrado aparte — nunca se muestran en el panel.',
    checkbox:
      'Entiendo que esta intake será grabada y procesada bajo los controles de privacidad de Caseflow.',
    privacyLink: 'Lea nuestra política de privacidad',
    start: 'Iniciar intake',
    back: 'Volver al inicio',
    sttNote:
      'Nota: el audio en vivo no se redacta por regex durante la llamada (limitación de STT). Hoja de ruta: redacción en el dispositivo.',
  },
} as const;
