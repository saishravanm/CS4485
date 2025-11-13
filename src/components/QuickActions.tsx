import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { 
  Home, 
  Utensils, 
  Heart, 
  Briefcase, 
  Phone, 
  MapPin 
} from "lucide-react";

interface QuickActionsProps {
  onActionClick: (action: string) => void;
}

export function QuickActions({ onActionClick }: QuickActionsProps) {
  const actions = [
    { id: 'shelter', label: 'Find Shelter', icon: Home, urgent: true },
    { id: 'food', label: 'Food Resources', icon: Utensils, urgent: true },
    { id: 'healthcare', label: 'Healthcare', icon: Heart, urgent: false },
    { id: 'employment', label: 'Job Help', icon: Briefcase, urgent: false },
    { id: 'emergency', label: 'Emergency', icon: Phone, urgent: true },
    { id: 'location', label: 'Nearby Services', icon: MapPin, urgent: false },
  ];

  return (
    <Card className="m-4 mt-0">
      <CardContent className="p-4">
        <h3 className="mb-3">Quick Actions</h3>
        <div className="grid grid-cols-2 gap-2">
          {actions.map((action) => {
            const Icon = action.icon;
            return (
              <Button
                key={action.id}
                variant={action.urgent ? "default" : "outline"}
                className="h-auto p-3 flex flex-col gap-1"
                onClick={() => onActionClick(action.id)}
              >
                <Icon className="w-5 h-5" />
                <span className="text-xs leading-tight text-center">
                  {action.label}
                </span>
              </Button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}