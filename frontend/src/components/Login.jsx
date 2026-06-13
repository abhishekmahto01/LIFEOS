// file: src/components/Login.js (or similar login component)

import React, { useState } from 'react';
import axios from 'axios';

export default function Login({ setAuthToken }) {
    const [credentials, setCredentials] = useState({ username: '', password: '' });
    const [error, setError] = useState('');

    const handleChange = (e) => {
        setCredentials({ ...credentials, [e.target.name]: e.target.value });
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        try {
            // 1. Clear any old tokens out of storage just in case
            localStorage.removeItem('token');
            
            // 2. Make the clean login request
            const response = await axios.post('/api/login', credentials);
            
            if (response.data.token) {
                // 3. Save new token and update app state
                localStorage.setItem('token', response.data.token);
                setAuthToken(response.data.token);
                window.location.href = '/dashboard'; // Redirect cleanly
            }
        } catch (err) {
            setError('Invalid username or password. Please try again.');
            console.error('Login Error:', err);
        }
    };

    return (
        <div className="login-container">
            <h2>Life OS Login</h2>
            {error && <p style={{ color: 'red' }}>{error}</p>}
            <form onSubmit={handleLogin}>
                <input type="text" name="username" placeholder="Username" onChange={handleChange} required />
                <input type="password" name="password" placeholder="Password" onChange={handleChange} required />
                <button type="submit">Login</button>
            </form>
        </div>
    );
}