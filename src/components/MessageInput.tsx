import { useState } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Send, Mic } from "lucide-react";

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
}

export function MessageInput({ onSendMessage, disabled }: MessageInputProps) {
  const [message, setMessage] = useState("");
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSendMessage(message.trim());
      setMessage("");
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 bg-background border-t">
      <div className="flex-1">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message or ask about resources..."
          disabled={disabled}
          className="min-h-[44px] max-h-32 resize-none"
          rows={1}
        />
      </div>
      
      <div className="flex flex-col gap-2">
        <Button
          type="submit"
          disabled={!message.trim() || disabled}
          size="sm"
          className="h-11 w-11 p-0"
        >
          <Send className="w-4 h-4" />
        </Button>
        
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-11 w-11 p-0"
          disabled={disabled}
        >
          <Mic className="w-4 h-4" />
        </Button>
      </div>
    </form>
  );
}