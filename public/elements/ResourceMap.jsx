//Note; requires env variable GOOGLE_MAPS_API_KEY=YOUR_REAL_KEY_HERE
//dm for key :) - AS

import React, { useState } from "react";

function buildDirectionsUrl(resources) {
  const addresses = (resources || [])
    .map((r) => r.streetAddress || r.address)
    .filter(Boolean);

  if (!addresses.length) return "";

  const [first, ...rest] = addresses;
  const base = "https://www.google.com/maps/dir/?api=1";
  const destination = `destination=${encodeURIComponent(first)}`;
  const waypoints = rest.length
    ? "&waypoints=" + encodeURIComponent(rest.join("|"))
    : "";

  return `${base}&${destination}${waypoints}`;
}

function buildStaticMapUrl(resources, apiKey) {
  if (!apiKey) return "";

  const markers = (resources || [])
    .map((r, i) => {
      const address = r.streetAddress || r.address;
      if (!address) return null;
      return `markers=label:${i + 1}|${encodeURIComponent(address)}`;
    })
    .filter(Boolean)
    .join("&");

  if (!markers) return "";

  return `https://maps.googleapis.com/maps/api/staticmap?size=800x450&maptype=roadmap&${markers}&key=${apiKey}`;
}

export default function ResourceMap() {
  //props are imported globally
  const { resources = [], googleMapsApiKey } = props || {};

  const directionsUrl = buildDirectionsUrl(resources);
  const staticUrl = buildStaticMapUrl(resources, googleMapsApiKey);
  const [imageOk, setImageOk] = useState(true);

  if (!directionsUrl) return null;

  const outerStyle = {
    width: "100%",
    maxWidth: "900px",
    margin: "1.5rem auto",
  };

  const cardStyle = {
    display: "block",
    borderRadius: "18px",
    overflow: "hidden",
    boxShadow: "0 8px 18px rgba(0,0,0,0.12)",
    border: "1px solid #e5e7eb",
    backgroundColor: "#ffffff",
    transform: "translateY(0)",
    transition:
      "box-shadow 150ms ease, transform 150ms ease, filter 150ms ease",
  };

  const cardHoverStyle = {
    boxShadow: "0 14px 28px rgba(0,0,0,0.18)",
    transform: "translateY(-2px)",
    filter: "brightness(1.02)",
  };

  const placeholderStyle = {
    width: "100%",
    height: "190px",
    backgroundColor: "#f3f4f6",
    color: "#6b7280",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.95rem",
  };

  return (
    <div style={outerStyle}>
      <a
        href={directionsUrl}
        target="_blank"
        rel="noreferrer"
        style={cardStyle}
        onMouseEnter={(e) => {
          Object.assign(e.currentTarget.style, cardHoverStyle);
        }}
        onMouseLeave={(e) => {
          Object.assign(e.currentTarget.style, {
            boxShadow: cardStyle.boxShadow,
            transform: cardStyle.transform,
            filter: "none",
          });
        }}
      >
        {staticUrl && imageOk ? (
          <img
            src={staticUrl}
            alt="Map"
            style={{ width: "100%", height: "auto", display: "block" }}
            onError={() => setImageOk(false)}
          />
        ) : (
          <div style={placeholderStyle}>View on Google Maps</div>
        )}
      </a>
    </div>
  );
}
