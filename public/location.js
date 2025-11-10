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
    
    function requestLocation() {
        if (!navigator.geolocation) {
            locationBox.innerHTML = '<span>📍 Location not supported</span>';
            locationBox.style.display = 'block';
            return;
        }
        
        // Show loading state
        locationBox.innerHTML = '<span>📍 Requesting location...</span>';
        locationBox.style.display = 'block';
        
        // Track if we have a location already (to avoid overwriting with errors)
        let hasLocation = false;
        
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
                sendLocationToBackend(lat, lng);
                
                // Optionally try to get more accurate location in the background
                // (silently update if successful, but don't show error if it fails)
                tryHighAccuracyLocation(hasLocation);
            },
            (error) => {
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
        try {
            // Try to use Chainlit's action API if available
            if (window.parent && window.parent.postMessage) {
                window.parent.postMessage({
                    type: 'chainlit-call-action',
                    name: 'set_location',
                    payload: {
                        latitude: latitude,
                        longitude: longitude
                    }
                }, '*');
                console.log('Location sent to backend:', latitude, longitude);
            } else if (window.chainlit && window.chainlit.sendAction) {
                // Alternative: direct Chainlit API if available
                window.chainlit.sendAction({
                    name: 'set_location',
                    payload: {
                        latitude: latitude,
                        longitude: longitude
                    }
                });
                console.log('Location sent to backend via chainlit API:', latitude, longitude);
            } else {
                console.warn('Chainlit action API not available, location not sent to backend');
            }
        } catch (error) {
            console.error('Error sending location to backend:', error);
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
                sendLocationToBackend(lat, lng);
            },
            (error) => {
                // Only show error if we don't already have a location
                if (!hasLocationAlready) {
                    let message = '📍 Location unavailable';
                    if (error.code === 1) {
                        message = '📍 Location denied';
                    } else if (error.code === 2) {
                        message = '📍 Location unavailable';
                    } else if (error.code === 3) {
                        message = '📍 Location timeout';
                    }
                    // Log error details for debugging
                    console.error('Location error:', error.code, error.message);
                    locationBox.innerHTML = `<span>${message}</span>`;
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
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLocationDisplay);
    } else {
        initLocationDisplay();
    }
})();

