import React, { useEffect, useMemo, useState } from 'react';
import type { AuthTokens } from './types';

type Props = {
  apiBase: string;
  onLoggedIn: (payload: { email: string; tokens: AuthTokens }) => void;
  onGoToSignup: () => void;
  initialEmail?: string;
};

function normalizeEmail(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) return '';
  return trimmed.toLowerCase();
}

export default function LoginScreen({ apiBase, onLoggedIn, onGoToSignup, initialEmail }: Props) {
  const [emailRaw, setEmailRaw] = useState('');
  const email = useMemo(() => normalizeEmail(emailRaw), [emailRaw]);

  const demoMode = (import.meta.env.VITE_DEMO_MODE || '').toLowerCase() === 'true';

  const [password, setPassword] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialEmail) setEmailRaw(initialEmail);
  }, [initialEmail]);

  const login = async () => {
    setError(null);
    if (!email || !email.includes('@')) {
      setError('Enter a valid email');
      return;
    }
    if (!password) {
      setError('Enter your password');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/email/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = (await res.json()) as AuthTokens & { detail?: string };
      if (!res.ok) throw new Error(data.detail || 'Login failed');
      onLoggedIn({ email, tokens: data });
    } catch (e: any) {
      setError(e.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const demoLogin = () => {
    setError(null);
    if (!email || !email.includes('@')) {
      setError('Enter a valid email');
      return;
    }
    onLoggedIn({
      email,
      tokens: {
        accessToken: 'demo',
        idToken: 'demo',
        refreshToken: null,
        expiresIn: null,
        tokenType: 'Bearer',
      },
    });
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 bg-gray-900">
      <div className="w-full max-w-md rounded-2xl bg-gray-800 shadow-2xl border border-white/10">
        <div className="px-6 pt-8 pb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-white">Skyro</h1>
              <p className="text-gray-300 mt-2">Login to order food on campus</p>
            </div>
            <button onClick={onGoToSignup} className="text-orange-400 hover:text-orange-300 font-semibold">
              Sign up
            </button>
          </div>

          {error && (
            <div className="mt-4 rounded-lg bg-red-600/20 border border-red-500/30 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <>
            <div className="mt-6">
              <label className="text-sm font-semibold text-gray-200">Email</label>
              <input
                value={emailRaw}
                onChange={(e) => setEmailRaw(e.target.value)}
                placeholder="you@college.edu"
                className="mt-2 w-full rounded-xl bg-gray-900/60 border border-white/10 px-4 py-3 text-white outline-none focus:ring-2 focus:ring-orange-500"
              />
            </div>

            <div className="mt-4">
              <label className="text-sm font-semibold text-gray-200">Password</label>
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                placeholder="••••••••"
                className="mt-2 w-full rounded-xl bg-gray-900/60 border border-white/10 px-4 py-3 text-white outline-none focus:ring-2 focus:ring-orange-500"
              />
              {demoMode && <p className="text-xs text-gray-400 mt-2">Demo mode is enabled. You can continue without password using the Demo button.</p>}
            </div>

            <button
              disabled={loading}
              onClick={login}
              className="mt-6 w-full rounded-xl bg-orange-500 hover:bg-orange-600 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold py-3"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>

            {demoMode && (
              <button
                disabled={loading}
                onClick={demoLogin}
                className="mt-3 w-full rounded-xl bg-gray-700 hover:bg-gray-600 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-3"
              >
                Continue (Demo)
              </button>
            )}

            <p className="text-xs text-gray-400 mt-4 leading-relaxed">
              By continuing, you agree to our Terms & Privacy Policy.
            </p>
          </>
        </div>
      </div>
    </div>
  );
}
