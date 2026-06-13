// file: src/components/Sidebar.js (or your navigation template)

import React, { useState } from 'react';
import { Link } from 'react-router-dom';

export default function Sidebar() {
    // Track which dropdown menus are open
    const [openMenus, setOpenMenus] = useState({
        analytics: false,
        productionPlanning: false,
        career: false // New state for Career dropdown
    });

    const toggleMenu = (menuName) => {
        setOpenMenus({ ...openMenus, [menuName]: !openMenus[menuName] });
    };

    return (
        <div className="sidebar-menu">
            <input type="text" placeholder="Search menu..." className="search-bar" />
            
            {/* Existing Dropdowns */}
            <div className="menu-item" onClick={() => toggleMenu('analytics')}>
                <span>Analytics</span> {openMenus.analytics ? '▼' : '▶'}
            </div>
            
            {/* ... Other existing menus ... */}

            {/* NEW: Career Module Dropdown Section */}
            <div className="menu-item" onClick={() => toggleMenu('career')}>
                <span>💼 Career Module</span> {openMenus.career ? '▼' : '▶'}
            </div>
            
            {openMenus.career && (
                <div className="sidebar-dropdown-submenus" style={{ paddingLeft: '15px' }}>
                    <Link to="/career/entry" className="sub-menu-item">
                        ➔ Job Entry Form
                    </Link>
                    <Link to="/career/history" className="sub-menu-item">
                        ➔ Application History
                    </Link>
                </div>
            )}
        </div>
    );
}