export async function callFirm(firmTestNumber: string, caseBriefText: string): Promise<unknown> {
  const res = await fetch('/api/twilio/call', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to: firmTestNumber, brief: caseBriefText }),
  });
  if (!res.ok) {
    throw new Error(`Twilio call failed: ${res.status}`);
  }
  return res.json();
}

export async function sendSMS(consumerPhone: string, message: string): Promise<unknown> {
  const res = await fetch('/api/twilio/sms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to: consumerPhone, message }),
  });
  if (!res.ok) {
    throw new Error(`Twilio SMS failed: ${res.status}`);
  }
  return res.json();
}
