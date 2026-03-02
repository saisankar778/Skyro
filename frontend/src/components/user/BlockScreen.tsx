import React from 'react';
import { DELIVERY_LOCATIONS } from '@/constants';

type Props = {
  selectedLocationId: string;
  onSelect: (id: string) => void;
  onBack: () => void;
  onNext: () => void;
};

export default function BlockScreen({ selectedLocationId, onSelect, onBack, onNext }: Props) {
  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gray-900">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-extrabold text-white">Select campus block</h2>
            <p className="text-gray-300 mt-1">This helps us deliver to the right location</p>
          </div>
          <button onClick={onBack} className="text-gray-200 hover:text-white font-semibold">
            Back
          </button>
        </div>

        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {DELIVERY_LOCATIONS.map((loc) => {
            const selected = loc.id === selectedLocationId;
            return (
              <button
                key={loc.id}
                onClick={() => onSelect(loc.id)}
                className={`text-left rounded-2xl border shadow-xl p-5 transition ${
                  selected
                    ? 'bg-orange-500/15 border-orange-500/40'
                    : 'bg-gray-800 border-white/10 hover:border-white/20'
                }`}
              >
                <p className="text-white font-extrabold text-lg">{loc.name}</p>
                <p className="text-gray-300 text-sm mt-2">Tap to select</p>
              </button>
            );
          })}
        </div>

        <button
          onClick={onNext}
          className="mt-8 w-full rounded-2xl bg-green-500 hover:bg-green-600 text-white font-extrabold py-4"
        >
          Proceed to payment
        </button>
      </div>
    </div>
  );
}
