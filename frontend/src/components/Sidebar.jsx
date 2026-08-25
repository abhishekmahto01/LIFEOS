// file: src/components/Sidebar.js (or your navigation template)

import React, { useState } from 'react';
import { Link } from 'react-router-dom';

export default function Sidebar() {
    // Track which dropdown menus are open
    const [openMenus, setOpenMenus] = useState({
        analytics: false,
        productionPlanning: false,
        career: false,
        socialMedia: false
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

            {/* Career Module Dropdown Section */}
            <div className="menu-item" onClick={() => toggleMenu('career')}>
                <span>💼 Career Module</span> {openMenus.career ? '▼' : '▶'}
            </div>
            
            {openMenus.career && (
                <div className="sidebar-dropdown-submenus" style={{ paddingLeft: '15px' }}>
                    <Link to="/career/job-entry" className="sub-menu-item">
                        ➔ Job Entry Form
                    </Link>
                    <Link to="/career/job-history" className="sub-menu-item">
                        ➔ Application History
                    </Link>
                </div>
            )}

            {/* Social Media Hub Dropdown Section */}
            <div className="menu-item" onClick={() => toggleMenu('socialMedia')}>
                <span>🌐 Social Media Hub</span> {openMenus.socialMedia ? '▼' : '▶'}
            </div>

            {openMenus.socialMedia && (
                <div className="sidebar-dropdown-submenus" style={{ paddingLeft: '15px' }}>
                    <Link to="/social-media" className="sub-menu-item">
                        ➔ Dashboard
                    </Link>
                    <Link to="/social-media/create" className="sub-menu-item">
                        ➔ Create Post
                    </Link>
                    <Link to="/social-media/calendar" className="sub-menu-item">
                        ➔ Content Calendar
                    </Link>
                    <Link to="/social-media/accounts" className="sub-menu-item">
                        ➔ Connected Accounts
                    </Link>
                    <Link to="/social-media/history" className="sub-menu-item">
                        ➔ Post History
                    </Link>
                    <Link to="/social-media/analytics" className="sub-menu-item">
                        ➔ Analytics
                    </Link>
                </div>
            )}
        </div>
    );
}