import { Resource } from "../components/ChatMessage";

export const mockResources: Record<string, Resource[]> = {
  shelter: [
    {
      id: "shelter-1",
      name: "City Emergency Shelter",
      type: "Emergency Shelter",
      address: "123 Main St, Downtown",
      phone: "(555) 123-4567",
      hours: "24/7 - Check-in after 6 PM",
      description: "Emergency overnight shelter with meals and basic services. No reservations required.",
      distance: "0.3 miles"
    },
    {
      id: "shelter-2",
      name: "Family Housing Center",
      type: "Family Shelter",
      address: "456 Oak Ave, Central District",
      phone: "(555) 234-5678",
      hours: "Check-in: 4-8 PM daily",
      description: "Temporary housing for families with children. Case management and childcare available.",
      distance: "0.7 miles"
    },
    {
      id: "shelter-3",
      name: "Veterans Housing Program",
      type: "Veterans Shelter",
      address: "789 Elm St, Westside",
      phone: "(555) 345-6789",
      hours: "24/7 - Veterans ID required",
      description: "Specialized housing and support services for homeless veterans.",
      distance: "1.2 miles"
    }
  ],
  food: [
    {
      id: "food-1",
      name: "Community Food Bank",
      type: "Food Pantry",
      address: "321 Church St, Downtown",
      phone: "(555) 456-7890",
      hours: "Mon-Fri: 9 AM - 4 PM, Sat: 9 AM - 12 PM",
      description: "Free groceries for individuals and families. Bring ID and proof of income if available.",
      distance: "0.4 miles"
    },
    {
      id: "food-2",
      name: "St. Mary's Soup Kitchen",
      type: "Meal Service",
      address: "654 Pine St, Central",
      phone: "(555) 567-8901",
      hours: "Lunch: 11:30 AM - 1 PM daily, Dinner: 5:30 - 7 PM daily",
      description: "Hot meals served daily. No questions asked, all are welcome.",
      distance: "0.6 miles"
    },
    {
      id: "food-3",
      name: "Mobile Food Truck",
      type: "Mobile Service",
      address: "City Park, varies by day",
      phone: "(555) 678-9012",
      hours: "Tue/Thu: 12-2 PM, Sat: 10 AM-12 PM",
      description: "Mobile food distribution. Check schedule for current location.",
      distance: "0.8 miles"
    }
  ],
  healthcare: [
    {
      id: "health-1",
      name: "Community Health Clinic",
      type: "Health Center",
      address: "987 Medical Dr, Health District",
      phone: "(555) 789-0123",
      hours: "Mon-Fri: 8 AM - 6 PM, Sat: 9 AM - 1 PM",
      description: "Free and low-cost medical care, dental services, and mental health support.",
      distance: "1.1 miles"
    },
    {
      id: "health-2",
      name: "Crisis Mental Health Center",
      type: "Mental Health",
      address: "147 Wellness Blvd, Central",
      phone: "(555) 890-1234",
      hours: "24/7 Crisis Line, Walk-ins: 8 AM - 8 PM",
      description: "Mental health crisis intervention, counseling, and substance abuse support.",
      distance: "0.9 miles"
    }
  ],
  employment: [
    {
      id: "job-1",
      name: "Workforce Development Center",
      type: "Employment Services",
      address: "258 Career Way, Business District",
      phone: "(555) 901-2345",
      hours: "Mon-Fri: 8 AM - 5 PM",
      description: "Job training, resume help, interview preparation, and employment placement services.",
      distance: "1.5 miles"
    },
    {
      id: "job-2",
      name: "Day Labor Center",
      type: "Temporary Work",
      address: "369 Work St, Industrial Area",
      phone: "(555) 012-3456",
      hours: "Mon-Fri: 6 AM - 12 PM",
      description: "Same-day temporary work opportunities. Arrive early for best selection.",
      distance: "2.1 miles"
    }
  ]
};

export const emergencyContacts = [
  { name: "911", number: "911", description: "Police, Fire, Medical Emergency" },
  { name: "Crisis Hotline", number: "988", description: "Suicide & Crisis Lifeline" },
  { name: "Homeless Hotline", number: "(555) 211-HELP", description: "24/7 Homeless Services" },
  { name: "Domestic Violence", number: "(555) 799-SAFE", description: "24/7 Domestic Violence Hotline" }
];

export const botResponses: Record<string, string> = {
  greeting: "Hello! I'm here to help you find resources and support services in your area. What do you need help with today?",
  shelter: "I found some shelter options near you. These provide safe places to stay overnight:",
  food: "Here are food resources where you can get meals and groceries:",
  healthcare: "I found healthcare services that provide free or low-cost medical care:",
  employment: "Here are employment and job training resources to help you find work:",
  emergency: "In case of emergency, here are important numbers to call:",
  location: "I can help you find services near your current location. What type of service are you looking for?",
  default: "I understand you're looking for help. I can assist you with finding shelter, food, healthcare, employment services, or emergency contacts. What would be most helpful right now?"
};