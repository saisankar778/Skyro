import React, { useContext } from 'react';
import { AppContext } from '../context/AppContext';
import { STATUS_COLORS, DRONE_STATUS_COLORS, RESTAURANTS, DELIVERY_LOCATIONS } from '../constants';
// FIX: Import UserIcon
import { DroneIcon, UserIcon } from './Icons';
import Map from './Map';
import { DroneStatus, OrderStatus } from '../types';

const StatsCard: React.FC<{ title: string; value: string | number, icon: React.ReactNode }> = ({ title, value, icon }) => (
    <div className="bg-gray-800 p-4 rounded-xl shadow-lg flex items-center space-x-4">
        <div className="bg-gray-700 p-3 rounded-full">
            {icon}
        </div>
        <div>
            <p className="text-gray-400 text-sm font-medium">{title}</p>
            <p className="text-2xl font-bold text-white">{value}</p>
        </div>
    </div>
);


const AdminView: React.FC = () => {
    const context = useContext(AppContext);
    
    if (!context) return null;

    const { orders, drones, activityLog, mapStyle, connectToDrone, disconnectFromDrone, commandRtl, updateDroneConnectionString, toggleMapStyle, updateOrderStatus } = context;

    const stats = {
        activeMissions: drones.filter(d => d.status === DroneStatus.ON_MISSION || d.status === DroneStatus.RETURNING_HOME).length,
        idleDrones: drones.filter(d => d.status === DroneStatus.IDLE).length,
        pendingOrders: orders.filter(o => o.status === 'Placed' || o.status === 'Accepted' || o.status === 'Cooking').length,
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col p-4 lg:p-8 max-w-screen-2xl mx-auto w-full">
            {/* Stats Bar */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
               <StatsCard title="Active Missions" value={stats.activeMissions} icon={<DroneIcon className="w-6 h-6 text-cyan-400"/>} />
               <StatsCard title="Idle Drones" value={stats.idleDrones} icon={<DroneIcon className="w-6 h-6 text-green-400"/>} />
               <StatsCard title="Pending Orders" value={stats.pendingOrders} icon={<UserIcon />} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 flex-grow">
                
                {/* Map Column */}
                <div className="lg:col-span-2 h-full flex flex-col bg-gray-800 p-4 rounded-xl shadow-2xl">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="font-bold text-xl">Live Fleet Map</h3>
                        <div className="flex items-center space-x-2 rounded-lg bg-gray-700 p-1">
                            <button onClick={toggleMapStyle} disabled={mapStyle==='schematic'} className={`px-3 py-1 text-sm rounded-md transition ${mapStyle==='schematic' ? 'bg-cyan-500 text-white' : 'hover:bg-gray-600'}`}>Schematic</button>
                            <button onClick={toggleMapStyle} disabled={mapStyle==='satellite'} className={`px-3 py-1 text-sm rounded-md transition ${mapStyle==='satellite' ? 'bg-cyan-500 text-white' : 'hover:bg-gray-600'}`}>Satellite</button>
                        </div>
                    </div>
                    <div className="flex-grow min-h-[400px]">
                        <Map 
                          mapStyle={mapStyle}
                          dronesToDisplay={drones}
                          restaurantsToDisplay={RESTAURANTS}
                          locationsToDisplay={DELIVERY_LOCATIONS}
                          showRestaurants={false}
                          showLocations={false}
                          showOnlyConnectedDrones={true}
                        />
                    </div>
                </div>
                
                {/* Controls & Logs Column */}
                <div className="h-full flex flex-col gap-8">
                    {/* Orders Management */}
                    <div className="bg-gray-800 p-4 rounded-xl shadow-2xl flex-1 flex flex-col">
                        <h3 className="font-bold text-xl mb-4">Orders Management</h3>
                        <div className="space-y-3 overflow-y-auto pr-2 flex-grow">
                            {orders.length === 0 ? (
                                <p className="text-gray-400">No orders yet.</p>
                            ) : (
                                orders.map(order => {
                                    const droneForOrder = drones.find(d => d.id === order.droneId);
                                    const terminalStatuses = [OrderStatus.DELIVERED, OrderStatus.DECLINED, OrderStatus.FAILED];
                                    const canDecline = order.status === OrderStatus.PLACED;
                                    const canCancel = !terminalStatuses.includes(order.status) && (!droneForOrder || droneForOrder.status !== DroneStatus.ON_MISSION);
                                    return (
                                        <div key={order.id} className="bg-gray-700/50 p-3 rounded-lg">
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex-1">
                                                    <p className="font-bold">{order.id}</p>
                                                    <p className="text-xs text-gray-400">User: {order.user} • Total: ${order.total.toFixed(2)} • Items: {order.items.length}</p>
                                                </div>
                                                <span className={`px-2 py-0.5 text-xs font-bold rounded-full text-white ${STATUS_COLORS[order.status]}`}>{order.status}</span>
                                            </div>
                                            <div className="mt-3 flex items-center justify-end gap-2">
                                                <button
                                                    onClick={() => updateOrderStatus(order.id, OrderStatus.DECLINED)}
                                                    disabled={!canDecline}
                                                    className={`px-3 py-1 text-sm rounded-lg font-bold transition ${canDecline ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-gray-600 text-gray-300 cursor-not-allowed'}`}
                                                >
                                                    Decline
                                                </button>
                                                <button
                                                    onClick={() => updateOrderStatus(order.id, OrderStatus.FAILED)}
                                                    disabled={!canCancel}
                                                    title={!canCancel ? 'Cannot cancel while drone is on a mission' : 'Cancel this order'}
                                                    className={`px-3 py-1 text-sm rounded-lg font-bold transition ${canCancel ? 'bg-yellow-500 hover:bg-yellow-600 text-black' : 'bg-gray-600 text-gray-300 cursor-not-allowed'}`}
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>

                    <div className="bg-gray-800 p-4 rounded-xl shadow-2xl flex-1 flex flex-col">
                        <h3 className="font-bold text-xl mb-4">Drone Fleet Control</h3>
                        <div className="space-y-4 overflow-y-auto pr-2 flex-grow">
                            {drones.map(drone => (
                                <div key={drone.id} className="bg-gray-700/50 p-3 rounded-lg">
                                    <div className="flex items-center space-x-3 mb-3">
                                        <DroneIcon className={`w-8 h-8 ${drone.isConnected ? 'text-cyan-400' : 'text-gray-500'}`} />
                                        <div className="flex-grow">
                                            <p className="font-bold">{drone.id} <span className="font-light text-gray-400 text-xs">({drone.model})</span></p>
                                            <div className="w-full bg-gray-600 rounded-full h-1.5 mt-1">
                                                <div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${drone.battery}%` }}></div>
                                            </div>
                                        </div>
                                        <button 
                                            onClick={() => commandRtl(drone.id)}
                                            disabled={!drone.isConnected || drone.status !== 'On Mission'}
                                            className="bg-red-500 hover:bg-red-600 text-white font-bold py-1 px-2 text-sm rounded disabled:bg-gray-600 disabled:cursor-not-allowed self-center">
                                            RTL
                                        </button>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <input 
                                            type="text"
                                            value={drone.connectionString}
                                            onChange={(e) => updateDroneConnectionString(drone.id, e.target.value)}
                                            className="flex-grow bg-gray-700 border border-gray-600 rounded-md py-1 px-2 text-sm focus:ring-cyan-500 focus:border-cyan-500"
                                            disabled={drone.isConnected}
                                        />
                                        {drone.isConnected ? (
                                            <button onClick={() => disconnectFromDrone(drone.id)} className="bg-red-500 hover:bg-red-600 text-white font-bold py-1 px-3 text-sm rounded-lg transition">Off</button>
                                        ) : (
                                            <button onClick={() => connectToDrone(drone.id)} className="bg-green-500 hover:bg-green-600 text-white font-bold py-1 px-3 text-sm rounded-lg transition">On</button>
                                        )}
                                    </div>
                                    <p className="text-xs mt-2 font-semibold text-gray-300">
                                        <span className={`inline-block w-2.5 h-2.5 rounded-full mr-1.5 ${DRONE_STATUS_COLORS[drone.status]}`}></span>
                                        {drone.status} {drone.isConnected ? <span className="text-green-400">(Connected)</span> : <span className="text-yellow-400">(Disconnected)</span>}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="bg-gray-800 p-4 rounded-xl shadow-2xl flex-1 flex flex-col">
                        <h3 className="font-bold text-xl mb-4">Activity Log</h3>
                        <div className="bg-gray-900 rounded-lg p-3 font-mono text-xs text-green-400 flex-grow overflow-y-auto flex flex-col-reverse max-h-80">
                            <div>
                                {activityLog.map((log, index) => (
                                    <p key={index} className="whitespace-pre-wrap leading-relaxed animate-fade-in">{log}</p>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AdminView;