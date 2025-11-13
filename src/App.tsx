import { useState, useRef, useEffect } from "react";
import { useChatSession, useChatMessages, useChatInteract } from "@chainlit/react-client";
import { ChatMessage, type Message, type Resource } from "./components/ChatMessage";
import { MessageInput } from "./components/MessageInput";
import { QuickActions } from "./components/QuickActions";
import { ChatHeader } from "./components/ChatHeader";
import { ScrollArea } from "./components/ui/scroll-area";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Phone } from "lucide-react";
import { mockResources, botResponses, emergencyContacts } from "./data/mockData";

import { v4 as uuid } from "uuid";
//import { talkToLex } from "./lexClient.ts.bak";

//const BOT_ID    = import.meta.env.VITE_LEX_BOT_ID as string;
//const ALIAS_ID  = import.meta.env.VITE_LEX_BOT_ALIAS_ID as string;
//const LOCALE_ID = import.meta.env.VITE_LEX_LOCALE_ID as string;

/* ---------- Helpers: extract JSON from bot text & normalize to Resource[] ---------- */

type AnyObj = Record<string, any>;

function tryExtractJson(text: string): { textWithoutJson: string; parsed?: any } {
  //strip markdown code fences if present
  const cleaned = text.replace(/```json|```/g, "").trim();

  //if the whole message is JSON
  try {
    const parsed = JSON.parse(cleaned);
    return { textWithoutJson: "", parsed };
  } catch {}

  //otherwise, find a JSON-looking block inside the text
  const start = Math.min(
    ...[cleaned.indexOf("{"), cleaned.indexOf("[")].filter((i) => i >= 0)
  );
  if (!Number.isFinite(start)) return { textWithoutJson: text };

  const lastCurly = cleaned.lastIndexOf("}");
  const lastSquare = cleaned.lastIndexOf("]");
  const end = Math.max(lastCurly, lastSquare);
  if (end <= start) return { textWithoutJson: text };

  const jsonChunk = cleaned.slice(start, end + 1);
  try {
    const parsed = JSON.parse(jsonChunk);
    const textWithoutJson = (cleaned.slice(0, start) + cleaned.slice(end + 1)).trim();
    return { textWithoutJson, parsed };
  } catch {
    return { textWithoutJson: text };
  }
}

function normalizeToResources(json: any): Resource[] {
  const toResource = (item: Record<string, any>): Resource => ({
    id: uuid(),
    name: item.name ?? "Unknown",
    type:
      item.type ??
      (typeof item.services === "string" &&
      item.services.toLowerCase().includes("shelter")
        ? "Emergency Shelter"
        : "Resource"),
    address: item.address ?? item.location ?? "Address not listed",
    phone: item.phone ?? item.number ?? "—",
    hours: item.hours ?? "Hours not listed",
    description: item.description ?? "",
    //array or comma seperated string
    services: Array.isArray(item.services)
      ? item.services
      : typeof item.services === "string"
      ? item.services.split(",").map((s: string) => s.trim())
      : [],
    distance: item.distance,
  });

  if (Array.isArray(json)) return json.map(toResource);
  if (json && typeof json === "object") {
    if (Array.isArray(json.shelters)) return json.shelters.map(toResource);
    if (Array.isArray(json.resources)) return json.resources.map(toResource);
    if (Array.isArray(json.results))   return json.results.map(toResource);
    return [toResource(json)];
  }
  return [];
}


/* --------------------------------- Component --------------------------------- */

export default function App() {
  // ---- Chainlit client hooks ----
  const sessionIdRef = useRef<string>();
  const { connect, disconnect } = useChatSession();
  const { messages: clMessages } = useChatMessages();
  const { sendMessage } = useChatInteract();

  useEffect(() => {
    sessionIdRef.current = crypto.randomUUID();
    connect({ userEnv: { sessionId: sessionIdRef.current } });
    return () => disconnect();
  }, [connect, disconnect]);

  // Mirror Chainlit assistant messages into our UI and keep JSON resource extraction
  useEffect(() => {
    if (!clMessages || clMessages.length === 0) return;
    const last = clMessages[clMessages.length - 1] as any;
    if (last?.author && String(last.author).toLowerCase() === "user") return;

    const raw = (typeof last?.output === "string")
      ? last.output
      : (last?.output?.[0]?.content ?? "");

    if (raw && typeof raw === "string") {
      const { textWithoutJson, parsed } = tryExtractJson(raw);
      const resources = parsed ? normalizeToResources(parsed) : undefined;
      const content =
        (textWithoutJson && textWithoutJson.trim()) ||
        (resources && resources.length > 0 ? "Here are some options I found:" : "(no response)");
      addBotMessage(content, resources);
    }
  }, [clMessages]);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      type: "bot",
      content: botResponses.greeting,
      timestamp: new Date(),
    },
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const simulateTyping = () => {
    setIsTyping(true);
    return new Promise((resolve) => {
      setTimeout(() => {
        setIsTyping(false);
        resolve(true);
      }, 1000 + Math.random() * 1000);
    });
  };

  const addBotMessage = async (content: string, resources?: Resource[]) => {
    await simulateTyping();

    const newMessage: Message = {
      id: Date.now().toString(),
      type: "bot",
      content,
      resources,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newMessage]);
  };

  const handleQuickAction = async (action: string) => {
    if (action === "emergency") {
      await addBotMessage(
        "Here are emergency contacts you can call right now:",
        emergencyContacts.map((contact) => ({
          id: contact.name,
          name: contact.name,
          type: "Emergency Contact",
          address: contact.description,
          phone: contact.number,
          hours: "24/7",
          description: contact.description,
        }))
      );
      return;
    }

    const utterance = getActionMessage(action);
    await handleSendMessage(utterance);
  };

  const getActionMessage = (action: string) => {
    const actionMessages: Record<string, string> = {
      shelter: "I need help finding shelter",
      food: "I need help finding food",
      healthcare: "I need healthcare services",
      employment: "I need help finding work",
      emergency: "I need emergency contacts",
      location: "Show me nearby services",
    };
    return actionMessages[action] || action;
  };

  const handleSendMessage = async (messageContent: string) => {
    // Add the user's message immediately for responsive UX
    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: messageContent,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);

    setIsTyping(true);
    try {
      // Send to Chainlit backend; bot response will arrive via clMessages effect
      await sendMessage({ content: messageContent });
    } catch (e: any) {
      console.error("Chainlit send error:", e);
      await addBotMessage(`Error sending to assistant: ${e?.message || "Unknown error"}`);
    } finally {
      setIsTyping(false);
    }
  };

  const handleEmergencyCall = () => {
    window.open("tel:911", "_self");
  };

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto bg-background">
      <ChatHeader onEmergencyCall={handleEmergencyCall} />

      <Alert className="m-4 mb-0 border-primary/30 bg-primary/10">
        <Phone className="h-4 w-4" />
        <AlertDescription>
          <strong>Emergency?</strong> Call 911 or tap the Emergency button above for immediate help.
        </AlertDescription>
      </Alert>

      <QuickActions onActionClick={handleQuickAction} />

      <ScrollArea className="flex-1 px-4">
        <div className="space-y-4 pb-4">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {isTyping && (
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                <div className="flex gap-1">
                  <div
                    className="w-1 h-1 bg-foreground rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <div
                    className="w-1 h-1 bg-foreground rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <div
                    className="w-1 h-1 bg-foreground rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              </div>
              <span className="text-sm text-muted-foreground">Resource Helper is typing...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      <MessageInput onSendMessage={handleSendMessage} disabled={isTyping} />
    </div>
  );
}
