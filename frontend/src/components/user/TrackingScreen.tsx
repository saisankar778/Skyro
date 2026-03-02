import React, { useContext, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, Check, MapPin, MoreVertical, Phone, Home } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { AppContext } from '../../context/AppContext';
import { DELIVERY_LOCATIONS, RESTAURANTS, STATUS_COLORS, HOME_LOCATION } from '../../constants';
import { Order, OrderStatus } from '../../types';
import Map from '../Map';

const toRad = (value: number) => (value * Math.PI) / 180;

const haversineMeters = (
  a: { lat: number; lon: number },
  b: { lat: number; lon: number },
) => {
  const R = 6371000;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);

  const sinDLat = Math.sin(dLat / 2);
  const sinDLon = Math.sin(dLon / 2);
  const h = sinDLat * sinDLat + Math.cos(lat1) * Math.cos(lat2) * sinDLon * sinDLon;
  const c = 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  return R * c;
};

const formatEta = (secondsTotal: number) => {
  if (!Number.isFinite(secondsTotal) || secondsTotal <= 0) return '--';
  const minutes = Math.round(secondsTotal / 60);
  if (minutes <= 0) return '1 min';
  return `${minutes} min${minutes === 1 ? '' : 's'}`;
};

const OrderStatusTracker: React.FC<{ order: Order }> = ({ order }) => {
  const statuses = [
    OrderStatus.PLACED,
    OrderStatus.COOKING,
    OrderStatus.READY_FOR_LAUNCH,
    OrderStatus.EN_ROUTE,
    OrderStatus.DELIVERED
  ];

  const currentStatusIndex = statuses.indexOf(order.status as OrderStatus);

  if (order.status === OrderStatus.DECLINED || order.status === OrderStatus.FAILED) {
    return (
      <div className="bg-red-50 p-4 rounded-xl border border-red-100 text-center">
        <p className="text-red-600 font-bold">Order {order.status === OrderStatus.DECLINED ? 'Declined' : 'Failed'}</p>
        <p className="text-red-400 text-sm mt-1">Please try again or contact support.</p>
      </div>
    )
  }

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{
        hidden: { opacity: 0 },
        show: { opacity: 1, transition: { staggerChildren: 0.06 } },
      }}
      className="relative pl-6 space-y-8 my-6"
    >
      {/* Vertical Line */}
      <div className="absolute left-[20px] top-2 bottom-2 w-0.5 bg-gray-200">
        <motion.div
          className="absolute top-0 w-full bg-green-500"
          initial={{ height: 0 }}
          animate={{ height: `${(currentStatusIndex / (statuses.length - 1)) * 100}%` }}
          transition={{ type: 'spring', stiffness: 120, damping: 18 }}
        />
      </div>

      {statuses.map((status, index) => {
        const isCompleted = index <= currentStatusIndex;
        const isCurrent = index === currentStatusIndex;

        return (
          <motion.div
            key={status}
            variants={{
              hidden: { opacity: 0, x: -14 },
              show: { opacity: 1, x: 0, transition: { type: 'spring', stiffness: 260, damping: 22 } },
            }}
            className="flex items-start gap-4"
          >
            <div className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors duration-300 ${isCompleted ? 'bg-green-500 border-green-500 text-white' : 'bg-white border-gray-300 text-gray-300'
              }`}>
              {isCompleted ? <Check size={14} strokeWidth={3} /> : <div className="w-2 h-2 rounded-full bg-gray-300"></div>}

              {isCurrent && (
                <span className="absolute inset-0 rounded-full bg-green-500/30 animate-ping"></span>
              )}
            </div>

            <div className={`${isCompleted ? 'opacity-100' : 'opacity-40'} transition-opacity`}>
              <h4 className={`text-sm font-bold ${isCurrent ? 'text-gray-900' : 'text-dark-text'}`}>{status}</h4>
              <p className="text-xs text-gray-500">
                {status === OrderStatus.PLACED && 'Order received by restaurant'}
                {status === OrderStatus.COOKING && 'Chef is preparing your food'}
                {status === OrderStatus.READY_FOR_LAUNCH && 'Drone is ready for takeoff'}
                {status === OrderStatus.EN_ROUTE && 'Drone is flying to your location'}
                {status === OrderStatus.DELIVERED && 'Enjoy your meal!'}
              </p>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
};

type Props = {
  userId: string;
  onBrowse: () => void;
};

export default function TrackingScreen({ userId, onBrowse }: Props) {
  const context = useContext(AppContext);
  const [isSheetExpanded, setIsSheetExpanded] = useState(false);
  const sheetScrollRef = useRef<HTMLDivElement>(null);
  const touchStartYRef = useRef<number | null>(null);

  const activeOrder = useMemo(
    () =>
      context?.orders.find(
        (o) =>
          o.user === userId,
      ),
    [context?.orders, userId],
  );

  const droneForOrder = context?.drones.find((d) => d.id === activeOrder?.droneId);
  const restaurantForOrder = RESTAURANTS.find((r) => r.id === activeOrder?.restaurantId);
  const locationForOrder = DELIVERY_LOCATIONS.find((l) => l.id === activeOrder?.deliveryLocationId);

  const estimatedTimeLabel = useMemo(() => {
    const speedMetersPerSecond = 5;
    if (!droneForOrder?.location) return '--';
    const home = droneForOrder.homeLocation || HOME_LOCATION;
    const dist = haversineMeters(droneForOrder.location, home);
    const seconds = dist / speedMetersPerSecond;
    return formatEta(seconds);
  }, [droneForOrder]);

  // QR Code View for Delivered status
  if (activeOrder?.status === OrderStatus.DELIVERED) {
    return (
      <div className="min-h-screen bg-green-50 flex flex-col items-center justify-center p-6 relative">
        <div className="w-full max-w-md bg-white rounded-3xl shadow-xl overflow-hidden text-center p-8 animate-fade-in-up">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6 text-green-600">
            <Check size={40} strokeWidth={3} />
          </div>

          <h2 className="text-2xl font-bold text-gray-800 mb-2">Order Delivered!</h2>
          <p className="text-gray-500 mb-8">
            Your package has arrived safely. Capture this QR code if verification is needed.
          </p>

          <div className="bg-gray-100 p-6 rounded-2xl inline-block mb-8">
            <QRCodeSVG value={activeOrder.id} size={180} />
            <p className="mt-3 font-mono text-sm font-bold text-gray-500">#{activeOrder.id}</p>
          </div>

          <button
            onClick={onBrowse}
            className="w-full py-4 bg-gray-900 text-white rounded-xl font-bold hover:bg-black transition-colors flex items-center justify-center gap-2"
          >
            <Home size={20} />
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="h-screen bg-gray-50 font-sans relative overflow-hidden"
    >
      <div className="absolute inset-0">
        {activeOrder ? (
          <>
            <motion.div
              initial={{ opacity: 0, scale: 1.02 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.45, ease: 'easeOut' }}
              className="absolute inset-0 z-0 bg-gray-200"
            >
              {activeOrder.status === OrderStatus.EN_ROUTE &&
                droneForOrder &&
                locationForOrder ? (
                <Map
                  dronesToDisplay={[
                    {
                      ...droneForOrder,
                      destination: locationForOrder.location,
                    },
                  ]}
                  restaurantsToDisplay={[]}
                  locationsToDisplay={[locationForOrder]}
                  showRestaurants={false}
                  showLocations={true}
                  showOnlyConnectedDrones={false}
                />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center bg-gray-100 text-gray-400">
                  <div className="w-20 h-20 bg-gray-200 rounded-full flex items-center justify-center mb-3 animate-pulse">
                    <MapPin size={32} />
                  </div>
                  <p className="text-sm font-medium">Map will activate when drone launches</p>
                </div>
              )}
            </motion.div>

            <div className="absolute inset-0 z-[900] pointer-events-none">
              <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-black/0 to-black/25" />
            </div>

            <motion.div
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
              className="absolute top-0 left-0 right-0 z-[1200] px-4 pt-3"
            >
              <div className="bg-white/75 backdrop-blur-xl border border-white/40 rounded-2xl shadow-[0_12px_35px_-15px_rgba(0,0,0,0.35)] px-3 py-2">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <button
                    onClick={onBrowse}
                    className="w-10 h-10 rounded-full bg-white/90 border border-white/50 shadow-sm flex items-center justify-center text-gray-800"
                    aria-label="Back"
                  >
                    <ArrowLeft size={18} />
                  </button>
                  <div>
                    <div className="text-[13px] font-extrabold text-dark-text leading-tight">Order #{activeOrder.id}</div>
                    <div className="text-[11px] text-gray-600 mt-0.5">{activeOrder.items.length} items, ₹{Math.round(activeOrder.total)}</div>
                  </div>
                </div>
                <button
                  className="w-10 h-10 rounded-full bg-white/90 border border-white/50 shadow-sm flex items-center justify-center text-gray-800"
                  aria-label="Menu"
                >
                  <MoreVertical size={18} />
                </button>
              </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ y: 22, opacity: 0 }}
              animate={{ y: 0, opacity: 1, height: isSheetExpanded ? '70vh' : '38vh' }}
              transition={{ type: 'spring', stiffness: 260, damping: 30 }}
              className="absolute left-0 right-0 bottom-0 z-[1300] bg-white/95 backdrop-blur-xl rounded-t-[28px] shadow-[0_-20px_60px_-25px_rgba(0,0,0,0.55)] border-t border-white/50 overflow-hidden"
            >
              <div className="pt-3 pb-2 flex items-center justify-center">
                <div className="w-12 h-1.5 bg-gray-300/80 rounded-full" />
              </div>

              <div
                ref={sheetScrollRef}
                className="px-4 pb-8 overflow-y-auto h-[calc(100%-20px)]"
                onWheel={(e) => {
                  if (!isSheetExpanded && e.deltaY < -30) {
                    setIsSheetExpanded(true);
                  }

                  if (
                    isSheetExpanded &&
                    sheetScrollRef.current &&
                    sheetScrollRef.current.scrollTop <= 0 &&
                    e.deltaY > 30
                  ) {
                    setIsSheetExpanded(false);
                  }
                }}
                onTouchStart={(e) => {
                  touchStartYRef.current = e.touches[0]?.clientY ?? null;
                }}
                onTouchMove={(e) => {
                  if (touchStartYRef.current == null) return;
                  const currentY = e.touches[0]?.clientY;
                  if (currentY == null) return;
                  const dy = currentY - touchStartYRef.current;

                  if (!isSheetExpanded && dy < -40) {
                    setIsSheetExpanded(true);
                    touchStartYRef.current = currentY;
                  }

                  if (
                    isSheetExpanded &&
                    sheetScrollRef.current &&
                    sheetScrollRef.current.scrollTop <= 0 &&
                    dy > 50
                  ) {
                    setIsSheetExpanded(false);
                    touchStartYRef.current = currentY;
                  }
                }}
                onTouchEnd={() => {
                  touchStartYRef.current = null;
                }}
              >
                <div className="pt-1 pb-5">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <div className="text-[22px] font-extrabold text-dark-text leading-tight">
                        Arriving in{' '}
                        <AnimatePresence mode="popLayout" initial={false}>
                          <motion.span
                            key={estimatedTimeLabel}
                            initial={{ opacity: 0, y: 8, filter: 'blur(2px)' }}
                            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                            exit={{ opacity: 0, y: -8, filter: 'blur(2px)' }}
                            transition={{ duration: 0.22, ease: 'easeOut' }}
                            className="inline-block ml-1"
                          >
                            {estimatedTimeLabel}
                          </motion.span>
                        </AnimatePresence>
                      </div>
                      <div className="text-[11px] text-gray-600 mt-1">To {locationForOrder?.name || 'destination'}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-gray-500 font-bold uppercase">Status</div>
                      <AnimatePresence mode="popLayout" initial={false}>
                        <motion.div
                          key={activeOrder.status}
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -6 }}
                          transition={{ duration: 0.2, ease: 'easeOut' }}
                          className="text-[12px] font-extrabold"
                          style={{ color: STATUS_COLORS[activeOrder.status] || '#111827' }}
                        >
                          {activeOrder.status}
                        </motion.div>
                      </AnimatePresence>
                    </div>
                  </div>
                </div>

                <h3 className="text-[13px] font-extrabold text-dark-text mb-2">Order Status</h3>
                <OrderStatusTracker order={activeOrder} />

                <div className="mt-4 bg-white/90 p-4 rounded-2xl shadow-sm border border-white/70 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-blue-50 rounded-full flex items-center justify-center text-2xl shadow-sm">
                      🚁
                    </div>
                    <div>
                      <p className="text-sm font-bold text-dark-text">Skyro Drone {droneForOrder?.model || 'X-1'}</p>
                      <p className="text-xs text-gray-600">Autonomous Delivery Partner</p>
                    </div>
                  </div>
                  <button className="w-11 h-11 bg-gray-100 rounded-full flex items-center justify-center text-gray-700 shadow-sm">
                    <Phone size={18} />
                  </button>
                </div>
              </div>
            </motion.div>

          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-[80vh] px-6 text-center">
            <div className="w-32 h-32 bg-orange-50 rounded-full flex items-center justify-center mb-6">
              <img src="https://cdni.iconscout.com/illustration/premium/thumb/empty-cart-7359550-6024618.png" alt="Empty" className="w-20 opacity-50" />
            </div>
            <h3 className="text-xl font-bold text-dark-text mb-2">No active orders</h3>
            <p className="text-gray-500 mb-8">Hungry? Order some delicious food now!</p>
            <button
              onClick={onBrowse}
              className="bg-brand-orange text-white px-8 py-3 rounded-xl font-bold hover:bg-orange-600 transition-colors shadow-lg"
            >
              Browse Restaurants
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
}
