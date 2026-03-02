import React, { useContext } from 'react';
import { AppContext } from '../context/AppContext';
import { Order, OrderStatus } from '../types';
import { STATUS_COLORS } from '../constants';
import { DroneIcon } from './Icons';

const OrderCard: React.FC<{ order: Order }> = ({ order }) => {
    const context = useContext(AppContext);

    const handleUpdate = (status: OrderStatus) => {
        context?.updateOrderStatus(order.id, status);
    };

    const handleLaunch = () => {
        context?.launchDroneForOrder(order.id);
    };
    
    const renderActions = () => {
        switch(order.status) {
            case OrderStatus.PLACED:
                return (
                    <>
                        <button onClick={() => handleUpdate(OrderStatus.ACCEPTED)} className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-lg transition">Accept</button>
                        <button onClick={() => handleUpdate(OrderStatus.DECLINED)} className="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-lg transition">Decline</button>
                    </>
                );
            case OrderStatus.ACCEPTED:
                return <button onClick={() => handleUpdate(OrderStatus.COOKING)} className="bg-yellow-500 hover:bg-yellow-600 text-black font-bold py-2 px-4 rounded-lg transition">Mark as Cooking</button>;
            case OrderStatus.COOKING:
                return <button onClick={() => handleUpdate(OrderStatus.READY_FOR_LAUNCH)} className="bg-purple-500 hover:bg-purple-600 text-white font-bold py-2 px-4 rounded-lg transition">Mark as Ready</button>;
            case OrderStatus.READY_FOR_LAUNCH:
                return <button onClick={handleLaunch} className="bg-cyan-500 hover:bg-cyan-600 text-white font-bold py-2 px-4 rounded-lg transition animate-pulse">Launch Drone</button>;
            default:
                return null;
        }
    };

    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow-lg border border-gray-700">
            <div className="flex justify-between items-center mb-3">
                <h3 className="font-bold text-lg">{order.id}</h3>
                <span className={`px-3 py-1 text-xs font-bold rounded-full text-white ${STATUS_COLORS[order.status]}`}>{order.status}</span>
            </div>
            <div className="text-sm text-gray-300">
                <p>Placed at: {order.createdAt.toLocaleTimeString()}</p>
                <ul className="my-2 list-disc list-inside">
                    {order.items.map(item => <li key={item.id}>{item.name} x {item.quantity}</li>)}
                </ul>
                <p className="font-semibold">Total: ${order.total.toFixed(2)}</p>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-700 flex justify-end space-x-2">
                {renderActions()}
            </div>
        </div>
    );
}

const VendorView: React.FC = () => {
    const context = useContext(AppContext);

    const activeOrders = context?.orders.filter(o => 
        o.status === OrderStatus.PLACED ||
        o.status === OrderStatus.ACCEPTED ||
        o.status === OrderStatus.COOKING ||
        o.status === OrderStatus.READY_FOR_LAUNCH
    ) || [];

    const completedOrders = context?.orders.filter(o => 
        o.status === OrderStatus.EN_ROUTE ||
        o.status === OrderStatus.DELIVERED ||
        o.status === OrderStatus.DECLINED
    ).slice(0, 10) || [];
    
    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col p-8 max-w-7xl mx-auto w-full overflow-hidden">
            <h2 className="text-3xl font-bold mb-6 text-yellow-300 border-b-2 border-yellow-300/20 pb-2">Restaurant Dashboard</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 flex-grow overflow-hidden">
                <div className="flex flex-col h-full min-h-0">
                    <h3 className="text-xl font-semibold mb-4">Active Orders ({activeOrders.length})</h3>
                    <div className="space-y-4 overflow-y-auto pr-2 flex-grow min-h-0">
                        {activeOrders.length > 0 ? (
                            activeOrders.map(order => <OrderCard key={order.id} order={order} />)
                        ) : (
                            <p className="text-gray-400">No active orders.</p>
                        )}
                    </div>
                </div>
                <div className="flex flex-col h-full min-h-0">
                    <h3 className="text-xl font-semibold mb-4">Recent History</h3>
                    <div className="space-y-2 overflow-y-auto pr-2 flex-grow min-h-0">
                        {completedOrders.map(order => (
                            <div key={order.id} className="bg-gray-800/50 p-3 rounded-md flex justify-between items-center text-sm">
                                <span>{order.id}</span>
                                <span className={`px-2 py-0.5 text-xs font-bold rounded-full text-white ${STATUS_COLORS[order.status]}`}>{order.status}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default VendorView;