"use client";

export default function ErrorBoundary({
  reset,
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  return (
    <main id="main">
      <h1>System status is temporarily unavailable.</h1>
      <button type="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
