// Location display functionality for HomeFinder
// Requests user location immediately on page load and sends to backend via Chainlit
(function() {
    'use strict';
    
    // console.log('📍 Location service initializing...');
    
    // Create location display box
    const locationBox = document.createElement('div');
    locationBox.id = 'location-display-box';
    locationBox.style.cssText = 'position: fixed; top: 10px; right: 10px; padding: 10px; background: rgba(0,0,0,0.8); color: white; border-radius: 5px; font-size: 12px; z-index: 10000; display: none;';
    locationBox.innerHTML = '<span>📍 Requesting location...</span>';
    
    // Helper function to update location display
    function updateLocationDisplay(message, isError = false) {
        locationBox.innerHTML = message;
        locationBox.style.display = 'block';
        locationBox.style.color = isError ? '#ff6b6b' : '#ffffff';
        // console.log(`📍 Location Display: ${message.replace(/<[^>]*>/g, '')}`);
    }
    
    // Wait for Chainlit to be ready
    function waitForChainlit(callback, maxAttempts = 20) {
        let attempts = 0;
        const checkInterval = setInterval(() => {
            attempts++;
            const chainlitReady = 
                window.chainlit || 
                window.parent?.chainlit ||
                document.querySelector('[data-chainlit]') ||
                document.querySelector('#chainlit-app');
            
            if (chainlitReady) {
                clearInterval(checkInterval);
                // console.log('✅ Chainlit detected and ready');
                callback();
            } else if (attempts >= maxAttempts) {
                clearInterval(checkInterval);
                // console.warn('⚠️ Chainlit not detected after max attempts, proceeding anyway...');
                callback();
            }
        }, 200);
    }
    
    // Send location to backend via Chainlit action
    function sendLocationToBackend(latitude, longitude) {
        // console.log(`📤 Attempting to send location to backend: (${latitude}, ${longitude})`);
        
        // Store in localStorage as backup
        try {
            if (typeof Storage !== 'undefined') {
                localStorage.setItem('user_location', JSON.stringify({
                    latitude: latitude,
                    longitude: longitude,
                    timestamp: new Date().toISOString()
                }));
                // console.log('💾 Location stored in localStorage as backup');
            }
        } catch (e) {
            // console.warn('⚠️ Could not store location in localStorage:', e);
        }
        
        let sent = false;
        const payload = {
            latitude: latitude,
            longitude: longitude
        };
        
        // Method 1: Try Chainlit's postMessage API (most reliable)
        try {
            const message = {
                type: 'chainlit-call-action',
                name: 'set_location',
                payload: payload
            };
            
            // Try multiple targets
            const targets = [
                { win: window.parent, name: 'parent' },
                { win: window.top, name: 'top' },
                { win: window, name: 'self' }
            ].filter(t => t.win && t.win.postMessage);
            
            for (const target of targets) {
                try {
                    target.win.postMessage(message, '*');
                    sent = true;
                    break;
                } catch (e) {
                    // Silently try next target
                }
            }
        } catch (error) {
            // Fall through to next method
        }
        
        // Method 2: Try direct Chainlit API
        if (!sent) {
            try {
                if (window.chainlit?.sendAction) {
                    window.chainlit.sendAction({
                        name: 'set_location',
                        payload: payload
                    });
                    sent = true;
                } else if (window.chainlit?.callAction) {
                    window.chainlit.callAction('set_location', payload);
                    sent = true;
                } else if (window.parent?.chainlit?.sendAction) {
                    window.parent.chainlit.sendAction({
                        name: 'set_location',
                        payload: payload
                    });
                    sent = true;
                }
            } catch (error) {
                // Fall through to next method
            }
        }
        
        // Method 3: Try using custom event
        if (!sent) {
            try {
                const event = new CustomEvent('chainlit-action', {
                    detail: {
                        name: 'set_location',
                        payload: payload
                    }
                });
                window.dispatchEvent(event);
                if (window.parent) {
                    window.parent.dispatchEvent(event);
                }
                sent = true; // Assume it worked
            } catch (error) {
                // All methods failed
            }
        }
        
        if (!sent) {
            console.warn('⚠️ Failed to send location to backend - stored in localStorage only');
        }
    }
    
    // Request user location
    function requestLocation() {
        // console.log('🔍 INITIATING LOCATION REQUEST...');
        updateLocationDisplay('<span>📍 Requesting location...</span>');
        
        // Mark that we're requesting to avoid duplicate requests
        if (window.locationRequestInProgress) {
            // console.log('⏳ Location request already in progress, skipping...');
            return;
        }
        window.locationRequestInProgress = true;
        
        // Check if geolocation is supported
        if (!navigator.geolocation) {
            const errorMsg = '📍 Location not supported by this browser';
            updateLocationDisplay(errorMsg, true);
            console.error('❌ LOCATION UNAVAILABLE: Browser does not support geolocation API');
            window.locationRequestInProgress = false; // Reset flag on error
            return;
        }
        
        // Check secure context
        const isSecureContext = window.isSecureContext || 
                               location.protocol === 'https:' || 
                               location.hostname === 'localhost' || 
                               location.hostname === '127.0.0.1';
        
        if (!isSecureContext) {
            const errorMsg = '📍 Location requires HTTPS or localhost';
            updateLocationDisplay(errorMsg, true);
            console.error('❌ SECURE CONTEXT REQUIRED:', {
                protocol: location.protocol,
                hostname: location.hostname,
                isSecureContext: window.isSecureContext
            });
            window.locationRequestInProgress = false; // Reset flag on error
            return;
        }
        
        // Check permissions (if available)
        if (navigator.permissions && navigator.permissions.query) {
            navigator.permissions.query({ name: 'geolocation' }).then((result) => {
                if (result.state === 'denied') {
                    const errorMsg = '📍 Location access denied<br><small style="font-size: 0.8em; opacity: 0.8;">Please allow location access in browser settings</small>';
                    updateLocationDisplay(errorMsg, true);
                    window.locationRequestInProgress = false;
                    return;
                }
            }).catch((err) => {
                // Permissions API not fully supported, continue anyway
            });
        }
        
        // Request location with standard accuracy first (faster, more reliable)
        const options = {
            enableHighAccuracy: false,
            timeout: 15000,
            maximumAge: 60000 // Allow cached location up to 1 minute old
        };
        
        navigator.geolocation.getCurrentPosition(
            // Success callback
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const accuracy = position.coords.accuracy;
                
                // Update display
                updateLocationDisplay(`
                    <span>📍 Location:</span><br>
                    <span style="font-size: 0.85em;">${lat.toFixed(6)}, ${lng.toFixed(6)}</span><br>
                    <small style="font-size: 0.75em; opacity: 0.8;">Accuracy: ${accuracy.toFixed(0)}m</small>
                `);
                
                // Send to backend
                waitForChainlit(() => {
                    sendLocationToBackend(lat, lng);
                    window.locationRequestInProgress = false; // Reset flag on success
                });
                
                // Optionally try high accuracy in background (silent update)
                setTimeout(() => {
                    navigator.geolocation.getCurrentPosition(
                        (highAccPosition) => {
                            const newLat = highAccPosition.coords.latitude;
                            const newLng = highAccPosition.coords.longitude;
                            const newAccuracy = highAccPosition.coords.accuracy;
                            
                            if (newAccuracy < accuracy) {
                                updateLocationDisplay(`
                                    <span>📍 Location:</span><br>
                                    <span style="font-size: 0.85em;">${newLat.toFixed(6)}, ${newLng.toFixed(6)}</span><br>
                                    <small style="font-size: 0.75em; opacity: 0.8;">Accuracy: ${newAccuracy.toFixed(0)}m</small>
                                `);
                                sendLocationToBackend(newLat, newLng);
                            }
                        },
                        (err) => {
                            // High-accuracy not available, using standard accuracy
                        },
                        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
                    );
                }, 2000);
            },
            // Error callback
            (error) => {
                let displayMsg = '';
                let helpText = '';
                
                switch (error.code) {
                    case 1: // PERMISSION_DENIED
                        displayMsg = '📍 Location access denied';
                        helpText = '<br><small style="font-size: 0.8em; opacity: 0.8;">Please allow location access in browser settings</small>';
                        break;
                    case 2: // POSITION_UNAVAILABLE
                        displayMsg = '📍 Location unavailable';
                        helpText = '<br><small style="font-size: 0.8em; opacity: 0.8;">Location services may be disabled. Check system settings.</small>';
                        break;
                    case 3: // TIMEOUT
                        displayMsg = '📍 Location timeout';
                        helpText = '<br><small style="font-size: 0.8em; opacity: 0.8;">Request took too long. You can still use the app by providing your location manually.</small>';
                        break;
                    default:
                        displayMsg = '📍 Location unavailable';
                        helpText = '<br><small style="font-size: 0.8em; opacity: 0.8;">Unknown error occurred</small>';
                }
                
                updateLocationDisplay(displayMsg + helpText, true);
                window.locationRequestInProgress = false; // Reset flag on error
            },
            options
        );
    }
    
    // Listen for location request triggers from backend
    function setupLocationRequestListener() {
        // Use MutationObserver to watch for new messages with location request trigger
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // Element node
                        // Check if this node or its children contain the trigger
                        const text = node.textContent || node.innerText || '';
                        if (text.includes('<location_request_trigger>REQUEST_LOCATION</location_request_trigger>')) {
                            // Check if we haven't already requested for this trigger
                            if (!node.dataset.locationRequested) {
                                node.dataset.locationRequested = 'true';
                                // console.log('📨 Received location request trigger from backend');
                                requestLocation();
                            }
                        }
                    }
                });
            });
        });
        
        // Start observing the document body for changes
        if (document.body) {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
            // console.log('✅ Location request listener set up');
        } else {
            // Wait for body to be ready
            setTimeout(setupLocationRequestListener, 100);
        }
    }
    
    // Retry sending stored location
    function retryStoredLocation() {
        try {
            const stored = localStorage.getItem('user_location');
            if (stored) {
                const location = JSON.parse(stored);
                const age = Date.now() - new Date(location.timestamp).getTime();
                const ageMinutes = Math.floor(age / 60000);
                
                if (age < 5 * 60 * 1000) { // Less than 5 minutes old
                    // console.log(`🔄 Retrying to send stored location (${ageMinutes} minutes old)`);
                    waitForChainlit(() => {
                        sendLocationToBackend(location.latitude, location.longitude);
                    });
                } else {
                    localStorage.removeItem('user_location');
                }
            }
        } catch (e) {
            console.warn('⚠️ Error checking stored location:', e);
        }
    }
    
    // Initialize location service
    function init() {
        // Append location box to body
        const container = document.body;
        if (container) {
            container.appendChild(locationBox);
            
            // Set up listener for location requests (don't request automatically on startup)
            setupLocationRequestListener();
        } else {
            setTimeout(init, 100);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            init();
            setTimeout(retryStoredLocation, 1000);
        });
    } else {
        init();
        setTimeout(retryStoredLocation, 1000);
    }
    
    // Retry when window becomes visible (in case page was in background)
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            setTimeout(retryStoredLocation, 500);
        }
    });
})();
