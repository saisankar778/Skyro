import React, { useMemo, useState } from 'react';
import { ArrowLeft, CreditCard, ShieldCheck, Wallet, Info } from 'lucide-react';
import { motion } from 'framer-motion';
import type { CartItem } from '../../types';
import type { RazorpayOrderResponse, RazorpaySuccessPayload } from './types';
import { loadScript } from '../../utils/loadScript';

declare global {
  interface Window {
    Razorpay?: any;
  }
}

type Props = {
  apiBase: string;
  accessToken: string;
  phone: string;
  cart: CartItem[];
  total: number;
  onBack: () => void;
  onPaymentVerified: () => void;
};

export default function PaymentScreen({ apiBase, accessToken, phone, cart, total, onBack, onPaymentVerified }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<'razorpay' | 'cod'>('razorpay');

  const demoMode = (import.meta.env.VITE_DEMO_MODE || '').toLowerCase() === 'true';

  const amountPaise = useMemo(() => Math.round(total * 100), [total]);

  const pay = async () => {
    setError(null);
    setLoading(true);
    try {
      if (demoMode || paymentMethod === 'cod') {
        const delay = demoMode ? 1500 : 1000;
        setTimeout(() => {
          onPaymentVerified();
        }, delay);
        return;
      }

      const orderRes = await fetch(`${apiBase}/api/payments/razorpay/order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ amount: amountPaise, currency: 'INR', receipt: `skyro-${Date.now()}` }),
      });

      const orderData = (await orderRes.json()) as RazorpayOrderResponse & { detail?: string };
      if (!orderRes.ok) throw new Error(orderData.detail || 'Failed to create payment order');

      await loadScript('https://checkout.razorpay.com/v1/checkout.js');
      if (!window.Razorpay) throw new Error('Razorpay SDK failed to load');

      const rzp = new window.Razorpay({
        key: orderData.keyId,
        amount: orderData.amount,
        currency: orderData.currency,
        order_id: orderData.orderId,
        name: 'Skyro',
        description: 'Campus food order',
        prefill: {
          contact: phone,
        },
        notes: {
          items: cart.map((i) => `${i.name} x ${i.quantity}`).join(', '),
        },
        theme: {
          color: '#FF6A00',
        },
        handler: async (response: RazorpaySuccessPayload) => {
          try {
            const verifyRes = await fetch(`${apiBase}/api/payments/razorpay/verify`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${accessToken}`,
              },
              body: JSON.stringify(response),
            });
            const verifyData = (await verifyRes.json()) as { verified?: boolean; detail?: string };
            if (!verifyRes.ok || !verifyData.verified) {
              throw new Error(verifyData.detail || 'Payment verification failed');
            }
            onPaymentVerified();
          } catch (e: any) {
            setError(e.message || 'Payment verification failed');
          } finally {
            setLoading(false);
          }
        },
        modal: {
          ondismiss: () => {
            setLoading(false);
          },
        },
      });

      rzp.open();
    } catch (e: any) {
      setError(e.message || 'Payment failed');
      setLoading(false);
    }
  };

  const fees = 25; // Delivery + Platform

  return (
    <div className="min-h-screen bg-warm-bg pb-10">
      {/* Header */}
      <div className="bg-white px-4 py-4 shadow-sm flex items-center gap-4 sticky top-0 z-10">
        <button onClick={onBack} className="p-2 hover:bg-gray-100 rounded-full transition-colors">
          <ArrowLeft size={20} className="text-gray-700" />
        </button>
        <div>
          <h2 className="text-lg font-bold text-dark-text">Payment Options</h2>
          <p className="text-xs text-gray-500">{cart.length} items • Total ₹{total + fees}</p>
        </div>
      </div>

      <div className="p-4 max-w-lg mx-auto space-y-6">

        {/* Offers Section */}
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
          <div className="flex items-start gap-3">
            <div className="bg-orange-100 p-2 rounded-full">
              <Wallet size={20} className="text-brand-orange" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-800">Bank Offers</h3>
              <p className="text-xs text-gray-500 mt-1">10% Instant Discount on HDFC Cards</p>
              <button className="text-brand-orange text-xs font-bold mt-2 uppercase">View More</button>
            </div>
          </div>
        </div>

        {/* Saved Options (Simulated) */}
        <div>
          <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3 px-1">Recommended</h3>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <button
              onClick={() => setPaymentMethod('razorpay')}
              disabled={loading}
              className={`w-full flex items-center justify-between p-4 transition-colors border-b border-gray-100 last:border-0 ${paymentMethod === 'razorpay' ? 'bg-orange-50/50' : 'hover:bg-gray-50'
                }`}
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                  <CreditCard size={20} className="text-gray-600" />
                </div>
                <div className="text-left">
                  <p className="font-bold text-gray-800">Razorpay Secure</p>
                  <p className="text-xs text-gray-500">Cards, UPI, Netbanking</p>
                </div>
              </div>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'razorpay' ? 'border-brand-orange' : 'border-gray-300'
                }`}>
                {paymentMethod === 'razorpay' && <div className="w-2.5 h-2.5 rounded-full bg-brand-orange"></div>}
              </div>
            </button>

            <button
              onClick={() => setPaymentMethod('cod')}
              disabled={loading}
              className={`w-full flex items-center justify-between p-4 transition-colors ${paymentMethod === 'cod' ? 'bg-orange-50/50' : 'hover:bg-gray-50'
                }`}
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                  <span className="text-xl">💸</span>
                </div>
                <div className="text-left">
                  <p className="font-bold text-gray-800">Cash on Delivery</p>
                  <p className="text-xs text-gray-500">Pay when drone arrives</p>
                </div>
              </div>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'cod' ? 'border-brand-orange' : 'border-gray-300'
                }`}>
                {paymentMethod === 'cod' && <div className="w-2.5 h-2.5 rounded-full bg-brand-orange"></div>}
              </div>
            </button>
          </div>
        </div>

        {error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-50 text-red-600 p-4 rounded-xl text-sm font-medium border border-red-100 flex items-center gap-2"
          >
            <Info size={16} />
            {error}
          </motion.div>
        )}

        {/* Footer info */}
        <div className="flex items-center justify-center gap-2 text-gray-400 mt-8">
          <ShieldCheck size={16} />
          <span className="text-xs font-medium">100% Secure & Safe Payments</span>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white border-t border-gray-100 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
        <button
          onClick={pay}
          disabled={loading}
          className="w-full bg-gradient-to-r from-brand-orange to-brand-red text-white p-4 rounded-xl font-bold shadow-lg shadow-orange-500/20 flex items-center justify-center gap-2 active:scale-[0.98] transition-all disabled:opacity-70 disabled:grayscale"
        >
          {loading ? 'Processing...' : (
            paymentMethod === 'cod' ? 'Place Order' : `Pay ₹${total + fees}`
          )}
        </button>
      </div>
    </div>
  );
}
