import React from 'react';
import { UserIcon, VendorIcon, AdminIcon, DroneIcon } from './Icons';

type View = 'user' | 'vendor' | 'admin';

interface HeaderProps {
    currentView: View;
    setView: (view: View) => void;
    canSwitchViews?: boolean;
}

const NavButton: React.FC<{
    isActive: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    label: string;
    activeColor: string;
}> = ({ isActive, onClick, icon, label, activeColor }) => {
    const activeClasses = `bg-${activeColor}-500 text-white`;
    const inactiveClasses = 'text-gray-300 hover:bg-gray-700 hover:text-white';

    return (
        <button
            onClick={onClick}
            className={`px-3 py-2 rounded-md text-sm font-medium flex items-center space-x-2 transition-colors ${isActive ? activeClasses : inactiveClasses}`}
        >
            {icon}
            <span>{label}</span>
        </button>
    );
};


const Header: React.FC<HeaderProps> = ({ currentView, setView, canSwitchViews = true }) => {
    return (
        <header className="bg-gray-800/50 backdrop-blur-sm shadow-lg fixed top-0 left-0 right-0 z-20">
            <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                    <div className="flex items-center">
                        <div className="flex-shrink-0 text-white flex items-center space-x-2">
                            <DroneIcon className="w-8 h-8 text-cyan-400"/>
                            <span className="font-bold text-xl">SkyWorks</span>
                        </div>
                    </div>
                    {canSwitchViews && (
                        <div className="hidden md:block">
                            <div className="ml-10 flex items-baseline space-x-4">
                                <NavButton
                                    isActive={currentView === 'user'}
                                    onClick={() => setView('user')}
                                    icon={<UserIcon />}
                                    label="User"
                                    activeColor="cyan"
                                />
                                <NavButton
                                    isActive={currentView === 'vendor'}
                                    onClick={() => setView('vendor')}
                                    icon={<VendorIcon />}
                                    label="Vendor"
                                    activeColor="yellow"
                                />
                                <NavButton
                                    isActive={currentView === 'admin'}
                                    onClick={() => setView('admin')}
                                    icon={<AdminIcon />}
                                    label="Admin"
                                    activeColor="red"
                                />
                            </div>
                        </div>
                    )}
                </div>
            </nav>
        </header>
    );
};

export default Header;
