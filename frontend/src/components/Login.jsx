import React, { useState } from 'react';
import authService from '../services/authService';

export default function Login({ setAuthToken }) {
    const [credentials, setCredentials] = useState({ username: '', password: '' });
    const [error, setError] = useState('');

    const handleChange = (e) => {
        setCredentials({ ...credentials, [e.target.name]: e.target.value });
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        try {
            const data = await authService.login(credentials.username, credentials.password);
            if (data.success && data.token) {
                if (setAuthToken) setAuthToken(data.token);
                window.location.href = '/dashboard';
            } else {
                setError(data.message || 'Invalid username or password.');
            }
        } catch (err) {
            setError(err.response?.data?.message || 'Invalid username or password. Please try again.');
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