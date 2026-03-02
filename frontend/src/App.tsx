import React, { useContext, useState } from 'react';
import UserView from './components/UserView';
import VendorView from './components/VendorView';
import AdminView from './components/AdminView';

import { AppProvider, AppContext } from './context/AppContext';
import { NotificationType } from './types';

const NOTIFICATION_BG_COLORS: Record<NotificationType, string> = {
    info: 'bg-blue-500',
    success: 'bg-green-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-600',
};

const NotificationContainer: React.FC = () => {
    const context = useContext(AppContext);
    if (!context) return null;

    const { notifications, removeNotification } = context;

    return (
        <div className="fixed top-20 right-4 z-50 w-full max-w-sm space-y-3">
            {notifications.map(notification => (
                <div
                    key={notification.id}
                    className={`relative flex items-center justify-between p-4 rounded-lg shadow-lg text-white ${NOTIFICATION_BG_COLORS[notification.type]} animate-slide-in-right`}
                >
                    <p className="font-semibold">{notification.message}</p>
                    <button onClick={() => removeNotification(notification.id)} className="ml-4 p-1 rounded-full hover:bg-white/20">&times;</button>
                </div>
            ))}
        </div>
    );
}

type View = 'user' | 'vendor' | 'admin';

const AppContent: React.FC = () => {
    const variant = (import.meta.env.VITE_VARIANT as View | undefined);
    const isLocked = Boolean(variant);
    const [view, setView] = useState<View>(variant ?? 'user');

    const activeView: View = isLocked ? (variant as View) : view;

    const renderView = () => {
        switch (activeView) {
            case 'user': return <UserView />;
            case 'vendor': return <VendorView />;
            case 'admin': return <AdminView />;
            default: return <UserView />; // Default to user view
        }
    };

    return (
        <div className="min-h-screen bg-warm-bg">
            <NotificationContainer />
            <main>
                {renderView()}
            </main>
        </div>
    );
}

const App: React.FC = () => {
    return (
        <AppProvider>
            <AppContent />
        </AppProvider>
    );
};

export default App;