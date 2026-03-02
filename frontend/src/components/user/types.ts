export type UserFlowStep = 'login' | 'signup' | 'food' | 'restaurant' | 'cart' | 'block' | 'payment' | 'tracking';

export interface EmailSignupResponse {
  ok: boolean;
}

export interface EmailConfirmResponse {
  ok: boolean;
}

export interface AuthTokens {
  accessToken: string;
  idToken: string;
  refreshToken?: string | null;
  expiresIn?: number | null;
  tokenType?: string | null;
}

export interface RazorpayOrderResponse {
  keyId: string;
  orderId: string;
  amount: number;
  currency: string;
}

export interface RazorpaySuccessPayload {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}
