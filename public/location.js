// Location service for HomeFinder
// Listens for trigger from backend, gets browser GPS, POSTs to /api/set_location
(function() {
    'use strict';
    
    window.locationRequestToken = null;
    window.locationRequestInProgress = false;
    
    // Send location to backend (or error if denied)
    async function sendLocationToBackend(latitude, longitude, error = null) {
        const token = window.locationRequestToken;
        if (!token) {
            console.error('❌ No token - cannot send location');
            return false;
        }
        
        const payload = error 
            ? { token, error: error.code, message: error.message }
            : { latitude, longitude, token };
        
        try {
            const response = await fetch('/api/set_location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            console.log(result.status === 'ok' ? '✅ Location sent' : '❌ Server error:', result);
            return result.status === 'ok';
        } catch (err) {
            console.error('❌ Failed to send location:', err);
            return false;
        }
    }
    
    // Request location from browser
    function requestLocation() {
        if (window.locationRequestInProgress) return;
        window.locationRequestInProgress = true;
        
        if (!navigator.geolocation) {
            console.error('❌ Geolocation not supported');
            window.locationRequestInProgress = false;
            return;
        }
        
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                console.log(`📍 Got location: (${lat}, ${lng})`);
                await sendLocationToBackend(lat, lng);
                window.locationRequestInProgress = false;
            },
            async (error) => {
                console.error('❌ Geolocation error:', error.code, error.message);
                // Notify backend of denial/error so it doesn't wait for timeout
                await sendLocationToBackend(null, null, error);
                window.locationRequestInProgress = false;
            },
            { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 }
        );
    }
    
    // Listen for trigger messages from backend
    function setupLocationRequestListener() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType !== 1) return;
                    
                    const text = node.textContent || '';
                    if (!text.includes('<location_request_trigger')) return;
                    if (node.dataset.locationRequested) return;
                    node.dataset.locationRequested = 'true';
                    
                    // Extract token
                    const match = text.match(/token="([^"]+)"/);
                    if (match) {
                        window.locationRequestToken = match[1];
                        console.log(`📨 Trigger received, token: ${match[1]}`);
                        requestLocation();
                    } else {
                        console.error('❌ Trigger found but no token');
                    }
                });
            });
        });
        
        if (document.body) {
            observer.observe(document.body, { childList: true, subtree: true });
        } else {
            setTimeout(setupLocationRequestListener, 100);
        }
    }
    
    // Init
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupLocationRequestListener);
    } else {
        setupLocationRequestListener();
    }
})();
