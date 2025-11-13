import { Avatar, AvatarFallback } from "./ui/avatar";
import { Button } from "./ui/button";
import { Bot, Menu, Phone } from "lucide-react";

interface ChatHeaderProps {
  onEmergencyCall: () => void;
}

export function ChatHeader({ onEmergencyCall }: ChatHeaderProps) {
  return (
    <header className="flex items-center justify-between p-4 bg-background border-b sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <Avatar className="w-10 h-10">
          <AvatarFallback className="bg-primary text-primary-foreground">
            <Bot className="w-5 h-5" />
          </AvatarFallback>
        </Avatar>
        <div>
          <h1 className="leading-tight">Resource Helper</h1>
          <p className="text-sm text-muted-foreground">
            Here to help you find resources
          </p>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        <Button
          variant="destructive"
          size="sm"
          onClick={onEmergencyCall}
          className="flex items-center gap-1"
        >
          <Phone className="w-4 h-4" />
          <span className="hidden sm:inline">Emergency</span>
        </Button>
        <Button variant="ghost" size="sm" className="sm:hidden">
          <Menu className="w-4 h-4" />
        </Button>
      </div>
    </header>
  );
}