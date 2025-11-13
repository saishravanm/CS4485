import { Avatar, AvatarFallback } from "./ui/avatar";
import { Card, CardContent } from "./ui/card";
import { Bot, User } from "lucide-react";
import { ResourceCard } from "./ResourceCard";

export interface Resource {
  id: string;
  name: string;
  type: string;
  address: string;
  phone: string;
  hours: string;
  description: string;
  distance?: string;
  services?: string[] | string
}

export interface Message {
  id: string;
  type: 'user' | 'bot';
  content: string;
  resources?: Resource[];
  timestamp: Date;
}

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isBot = message.type === 'bot';
  
  return (
    <div className={`flex gap-3 ${isBot ? 'justify-start' : 'justify-end'} mb-4`}>
      {isBot && (
        <Avatar className="w-8 h-8 mt-1">
          <AvatarFallback className="bg-primary text-primary-foreground">
            <Bot className="w-4 h-4" />
          </AvatarFallback>
        </Avatar>
      )}
      
      <div className={`max-w-[80%] ${isBot ? 'order-2' : 'order-1'}`}>
        <Card className={`${isBot ? 'bg-muted' : 'bg-primary text-primary-foreground'}`}>
          <CardContent className="p-3">
            <p className="mb-0">{message.content}</p>
          </CardContent>
        </Card>
        
        {message.resources && message.resources.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.resources.map((resource) => (
              <ResourceCard key={resource.id} resource={resource} />
            ))}
          </div>
        )}
        
        <p className="mt-1 px-1 opacity-60 text-xs">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
      
      {!isBot && (
        <Avatar className="w-8 h-8 mt-1">
          <AvatarFallback className="bg-secondary text-secondary-foreground">
            <User className="w-4 h-4" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}