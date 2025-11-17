// Location display functionality
(function() {
    // Create location display box
    const locationBox = document.createElement('div');
    locationBox.id = 'location-display-box';
    locationBox.style.display = 'none'; // Hidden until location is received
    
    // Wait for DOM to be ready
    function initLocationDisplay() {
        // Append to body or a container that exists in Chainlit
        const container = document.body;
        if (container) {
            container.appendChild(locationBox);
            
            // Request location permission and get coordinates
            requestLocation();
        } else {
            // Retry if body not ready
            setTimeout(initLocationDisplay, 100);
        }
    }
    
    // Wait for Chainlit to be ready (check for Chainlit-specific elements/APIs)
    function waitForChainlit(callback, maxAttempts = 20) {
        let attempts = 0;
        const checkInterval = setInterval(() => {
            attempts++;
            // Check if Chainlit is ready (look for Chainlit-specific elements or APIs)
            const chainlitReady = 
                window.chainlit || 
                window.parent?.chainlit ||
                document.querySelector('[data-chainlit]') ||
                document.querySelector('#chainlit-app');
            
            if (chainlitReady || attempts >= maxAttempts) {
                clearInterval(checkInterval);
                callback();
            }
        }, 200); // Check every 200ms
    }
    
    function requestLocation() {
        if (!navigator.geolocation) {
            locationBox.innerHTML = '<span>📍 Location not supported</span>';
            locationBox.style.display = 'block';
            return;
        }
        
        // Check if we're in a secure context (HTTPS or localhost)
        const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        if (!isSecureContext) {
            locationBox.innerHTML = '<span>📍 Location requires HTTPS or localhost</span>';
            locationBox.style.display = 'block';
            console.error('Geolocation requires secure context (HTTPS or localhost)');
            return;
        }
        
        // Check if we're in an iframe (which can cause location issues)
        const inIframe = window.self !== window.top;
        if (inIframe) {
            console.warn('Running in iframe - location may be restricted. Iframe context:', {
                sameOrigin: window.location.origin === window.top.location.origin,
                parentOrigin: window.top.location.origin
            });
        }
        
        // Check permissions API if available
        if (navigator.permissions && navigator.permissions.query) {
            navigator.permissions.query({ name: 'geolocation' }).then((result) => {
                console.log('Geolocation permission status:', result.state);
                if (result.state === 'denied') {
                    locationBox.innerHTML = '<span>📍 Location denied</span><br><small style="font-size: 0.8em; opacity: 0.8;">Please allow location access in your browser settings</small>';
                    locationBox.style.display = 'block';
                    return;
                }
            }).catch((err) => {
                console.warn('Permissions API not fully supported:', err);
            });
        }
        
        // Show loading state
        locationBox.innerHTML = '<span>📍 Requesting location...</span>';
        locationBox.style.display = 'block';
        
        // Track if we have a location already (to avoid overwriting with errors)
        let hasLocation = false;
        
        console.log('Requesting location with options:', {
            enableHighAccuracy: false,
            timeout: 15000,
            maximumAge: 60000
        });
        
        // First try with standard accuracy (faster, more reliable)
        // This allows cached locations and doesn't require GPS
        navigator.geolocation.getCurrentPosition(
            (position) => {
                // Success - display coordinates
                hasLocation = true;
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const latDisplay = lat.toFixed(6);
                const lngDisplay = lng.toFixed(6);
                locationBox.innerHTML = `
                    <span>📍 Location:</span><br>
                    <span style="font-size: 0.85em;">${latDisplay}, ${lngDisplay}</span>
                `;
                locationBox.style.display = 'block';
                
                // Send location to backend via Chainlit action
                // Wait for Chainlit to be ready before sending
                waitForChainlit(() => {
                    sendLocationToBackend(lat, lng);
                });
                
                // Optionally try to get more accurate location in the background
                // (silently update if successful, but don't show error if it fails)
                tryHighAccuracyLocation(hasLocation);
            },
            (error) => {
                // Log detailed error information
                console.error('Standard location request failed:', {
                    code: error.code,
                    message: error.message,
                    codeName: error.code === 1 ? 'PERMISSION_DENIED' : error.code === 2 ? 'POSITION_UNAVAILABLE' : error.code === 3 ? 'TIMEOUT' : 'UNKNOWN',
                    secureContext: window.isSecureContext,
                    protocol: location.protocol,
                    hostname: location.hostname
                });
                
                // If standard accuracy fails, try with high accuracy as fallback
                console.log('Standard location failed, trying high accuracy:', error.code);
                tryHighAccuracyLocation(hasLocation);
            },
            {
                enableHighAccuracy: false, // Start with standard accuracy
                timeout: 15000, // Increased timeout
                maximumAge: 60000 // Allow cached location up to 1 minute old
            }
        );
    }
    
    // Send location to backend via Chainlit action
    function sendLocationToBackend(latitude, longitude) {
        // Store in localStorage as backup (works in incognito mode in modern browsers)
        try {
            // Test if localStorage is available (works in incognito, but may be disabled)
            if (typeof Storage !== 'undefined') {
                localStorage.setItem('user_location', JSON.stringify({
                    latitude: latitude,
                    longitude: longitude,
                    timestamp: new Date().toISOString()
                }));
            }
        } catch (e) {
            // localStorage might be disabled or full - that's okay, it's just a backup
            console.warn('Could not store location in localStorage (this is okay, it\'s just a backup):', e);
        }
        
        let sent = false;
        
        // Method 1: Try Chainlit's postMessage API (most reliable)
        try {
            // Try multiple postMessage targets
            const targets = [
                window.parent,
                window.top,
                window
            ].filter(t => t && t.postMessage);
            
            for (const target of targets) {
                try {
                    target.postMessage({
                        type: 'chainlit-call-action',
                        name: 'set_location',
                        payload: {
                            latitude: latitude,
                            longitude: longitude
                        }
                    }, '*');
                    console.log('Location sent via postMessage to', target === window.parent ? 'parent' : target === window.top ? 'top' : 'self', ':', latitude, longitude);
                    sent = true;
                    break; // If one succeeds, stop trying
                } catch (e) {
                    console.warn('postMessage to target failed:', e);
                }
            }
        } catch (error) {
            console.warn('postMessage method failed:', error);
        }
        
        // Method 2: Try direct Chainlit API if available
        if (!sent) {
            try {
                if (window.chainlit && window.chainlit.sendAction) {
                    window.chainlit.sendAction({
                        name: 'set_location',
                        payload: {
                            latitude: latitude,
                            longitude: longitude
                        }
                    });
                    console.log('Location sent via chainlit.sendAction:', latitude, longitude);
                    sent = true;
                }
            } catch (error) {
                console.warn('chainlit.sendAction method failed:', error);
            }
        }
        
        // Method 3: Try using fetch to send to a custom endpoint (if available)
        if (!sent) {
            try {
                // Try to send via fetch as last resort
                fetch('/api/location', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        latitude: latitude,
                        longitude: longitude
                    })
                }).then(response => {
                    if (response.ok) {
                        console.log('Location sent via fetch API:', latitude, longitude);
                        sent = true;
                    }
                }).catch(err => {
                    console.warn('Fetch API method failed:', err);
                });
            } catch (error) {
                console.warn('Fetch method failed:', error);
            }
        }
        
        if (!sent) {
            console.warn('All methods failed - location stored in localStorage only. Will be sent with first message.');
        }
    }
    
    // Separate function to try high accuracy location (optional refinement)
    function tryHighAccuracyLocation(hasLocationAlready) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                // Success with high accuracy - update display
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const latDisplay = lat.toFixed(6);
                const lngDisplay = lng.toFixed(6);
                locationBox.innerHTML = `
                    <span>📍 Location:</span><br>
                    <span style="font-size: 0.85em;">${latDisplay}, ${lngDisplay}</span>
                `;
                locationBox.style.display = 'block';
                
                // Send updated high-accuracy location to backend
                waitForChainlit(() => {
                    sendLocationToBackend(lat, lng);
                });
            },
            (error) => {
                // Only show error if we don't already have a location
                if (!hasLocationAlready) {
                    let message = '📍 Location unavailable';
                    let helpText = '';
                    
                    if (error.code === 1) {
                        // PERMISSION_DENIED
                        message = '📍 Location access denied';
                        helpText = '<br><small style="font-size: 0.8em; opacity: 0.8;">Please allow location access in your browser settings</small>';
                    } else if (error.code === 2) {
                        // POSITION_UNAVAILABLE
                        message = '📍 Location unavailable';
                        helpText = '<br><small style="font-size: 0.8em; opacity: 0.8;">Location services may be disabled. Check your system settings.</small>';
                    } else if (error.code === 3) {
                        // TIMEOUT
                        message = '📍 Location timeout';
                        helpText = '<br><small style="font-size: 0.8em; opacity: 0.8;">Location request took too long. You can still use the app by providing your location manually.</small>';
                    }
                    
                    // Log error details for debugging
                    console.error('Location error:', {
                        code: error.code,
                        message: error.message,
                        codeName: error.code === 1 ? 'PERMISSION_DENIED' : error.code === 2 ? 'POSITION_UNAVAILABLE' : error.code === 3 ? 'TIMEOUT' : 'UNKNOWN'
                    });
                    
                    locationBox.innerHTML = `<span>${message}${helpText}</span>`;
                    locationBox.style.display = 'block';
                }
                // If we already have a location, silently fail (don't overwrite)
            },
            {
                enableHighAccuracy: true, // Try GPS for better accuracy
                timeout: 20000, // Longer timeout for GPS
                maximumAge: 0 // Don't use cached for high accuracy attempt
            }
        );
    }
    
    // Check for stored location and retry sending it
    function retryStoredLocation() {
        try {
            const stored = localStorage.getItem('user_location');
            if (stored) {
                const location = JSON.parse(stored);
                const age = Date.now() - new Date(location.timestamp).getTime();
                // Only retry if location is less than 5 minutes old
                if (age < 5 * 60 * 1000) {
                    console.log('Retrying to send stored location:', location);
                    // Wait for Chainlit to be ready before retrying
                    waitForChainlit(() => {
                        sendLocationToBackend(location.latitude, location.longitude);
                    });
                } else {
                    // Remove stale location
                    localStorage.removeItem('user_location');
                }
            }
        } catch (e) {
            console.warn('Error checking stored location:', e);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initLocationDisplay();
            // Retry sending stored location after a short delay to ensure Chainlit is ready
            setTimeout(retryStoredLocation, 1000);
        });
    } else {
        initLocationDisplay();
        // Retry sending stored location after a short delay
        setTimeout(retryStoredLocation, 1000);
    }
    
    // Also retry when window becomes visible (in case page was in background)
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            setTimeout(retryStoredLocation, 500);
        }
    });
})();

