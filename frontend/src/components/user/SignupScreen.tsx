import React, { useMemo, useState } from 'react';

type Props = {
  apiBase: string;
  onBackToLogin: () => void;
  onSignupComplete: (email: string) => void;
};

function normalizeEmail(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) return '';
  return trimmed.toLowerCase();
}

export default function SignupScreen({ apiBase, onBackToLogin, onSignupComplete }: Props) {
  const [stage, setStage] = useState<'form' | 'confirm'>('form');

  const [emailRaw, setEmailRaw] = useState('');
  const email = useMemo(() => normalizeEmail(emailRaw), [emailRaw]);
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const signup = async () => {
    setError(null);
    if (!email || !email.includes('@')) {
      setError('Enter a valid email');
      return;
    }
    if (!password) {
      setError('Enter a password');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/email/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = (await res.json()) as { ok?: boolean; detail?: string };
      if (!res.ok) throw new Error(data.detail || 'Signup failed');
      setStage('confirm');
    } catch (e: any) {
      setError(e.message || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  const confirm = async () => {
    setError(null);
    if (!email || !email.includes('@')) {
      setError('Enter a valid email');
      return;
    }
    if (!code.trim()) {
      setError('Enter verification code');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/email/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code: code.trim() }),
      });
      const data = (await res.json()) as { ok?: boolean; detail?: string };
      if (!res.ok) throw new Error(data.detail || 'Verification failed');
      onSignupComplete(email);
    } catch (e: any) {
      setError(e.message || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 bg-gray-900">
      <div className="w-full max-w-md rounded-2xl bg-gray-800 shadow-2xl border border-white/10">
        <div className="px-6 pt-8 pb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-white">Create Skyro account</h1>
              <p className="text-gray-300 mt-2">Sign up with your email</p>
            </div>
            <button onClick={onBackToLogin} className="text-orange-400 hover:text-orange-300 font-semibold">
              Sign in
            </button>
          </div>

          {error && (
            <div className="mt-4 rounded-lg bg-red-600/20 border border-red-500/30 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {stage === 'form' ? (
            <>
              <div className="mt-6">
                <label className="text-sm font-semibold text-gray-200">Email</label>
                <input
                  value={emailRaw}
                  onChange={(e) => setEmailRaw(e.target.value)}
                  placeholder="you@college.edu"
                  className="mt-2 w-full rounded-xl bg-gray-900/60 border border-white/10 px-4 py-3 text-white outline-none focus:ring-2 focus:ring-orange-500"
                />
                <p className="text-xs text-gray-400 mt-2">We’ll send a verification code to this email.</p>
              </div>

              <div className="mt-4">
                <label className="text-sm font-semibold text-gray-200">Password</label>
                <input
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type="password"
                  placeholder="Create a password"
                  className="mt-2 w-full rounded-xl bg-gray-900/60 border border-white/10 px-4 py-3 text-white outline-none focus:ring-2 focus:ring-orange-500"
                />
              </div>

              <button
                disabled={loading}
                onClick={signup}
                className="mt-6 w-full rounded-xl bg-orange-500 hover:bg-orange-600 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold py-3"
              >
                {loading ? 'Creating...' : 'Create account'}
              </button>
            </>
          ) : (
            <>
              <div className="mt-6">
                <p className="text-sm text-gray-200 font-semibold">Verify your email</p>
                <p className="text-xs text-gray-400 mt-1">Enter the code sent to {email}</p>

                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  inputMode="numeric"
                  placeholder="123456"
                  className="mt-3 w-full rounded-xl bg-gray-900/60 border border-white/10 px-4 py-3 text-white outline-none focus:ring-2 focus:ring-orange-500 tracking-widest"
                />
              </div>

              <button
                disabled={loading}
                onClick={confirm}
                className="mt-6 w-full rounded-xl bg-orange-500 hover:bg-orange-600 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold py-3"
              >
                {loading ? 'Verifying...' : 'Verify & Continue'}
              </button>

              <button
                disabled={loading}
                onClick={() => {
                  setStage('form');
                  setCode('');
                  setError(null);
                }}
                className="mt-3 w-full rounded-xl bg-gray-700 hover:bg-gray-600 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-3"
              >
                Change email
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
