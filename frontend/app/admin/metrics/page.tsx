import { redirect } from 'next/navigation';

/** Legacy path — metrics live inside the firm dashboard for all signed-in users. */
export default function AdminMetricsPage() {
  redirect('/firm');
}
