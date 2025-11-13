import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { MapPin, Phone, Clock } from "lucide-react";
import { Resource } from "./ChatMessage";

interface ResourceCardProps {
  resource: Resource;
}

export function ResourceCard({ resource }: ResourceCardProps) {
  const handleCall = () => {
    if (!resource.phone) return;
    const tel = resource.phone.replace(/[^0-9+]/g, "");
    window.open(`tel:${tel}`, "_self");
  };

  const handleDirections = () => {
    if (!resource.address) return;
    const address = encodeURIComponent(resource.address);
    window.open(`https://maps.google.com?q=${address}`, "_blank");
  };

  // NEW: normalize services → string[]
  const servicesArray =
    Array.isArray(resource.services)
      ? resource.services
      : typeof (resource as any).services === "string"
      ? (resource as any).services.split(",").map((s) => s.trim()).filter(Boolean)
      : [];

  return (
    <Card className="border-l-4 border-l-primary">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-tight">{resource.name}</CardTitle>

          {/* NEW: multiple badges (fallback to single type) */}
          <div className="flex flex-wrap gap-2 justify-end shrink-0 max-w-[60%]">
            {servicesArray.length > 0
              ? servicesArray.map((service) => (
                  <Badge
                    key={service}
                    variant="secondary"
                    className="text-xs whitespace-nowrap"
                  >
                    {service}
                  </Badge>
                ))
              : resource.type && (
                  <Badge variant="secondary" className="text-xs whitespace-nowrap">
                    {resource.type}
                  </Badge>
                )}
          </div>
        </div>

        {resource.distance && (
          <Badge variant="outline" className="w-fit">
            {resource.distance}
          </Badge>
        )}
      </CardHeader>

      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{resource.description}</p>

        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 mt-0.5 text-muted-foreground flex-shrink-0" />
            <span className="text-sm">{resource.address}</span>
          </div>

          <div className="flex items-center gap-2">
            <Phone className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <span className="text-sm">{resource.phone}</span>
          </div>

          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <span className="text-sm">{resource.hours || "Hours not listed"}</span>
          </div>
        </div>

        <div className="flex gap-2 pt-2">
          <Button onClick={handleCall} size="sm" className="flex-1">
            <Phone className="w-4 h-4 mr-1" />
            Call
          </Button>
          <Button onClick={handleDirections} variant="outline" size="sm" className="flex-1">
            <MapPin className="w-4 h-4 mr-1" />
            Directions
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
