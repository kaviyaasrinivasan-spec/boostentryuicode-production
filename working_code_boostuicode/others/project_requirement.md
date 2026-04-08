# WhatsApp API Requirements - Vehicle Hire Project

## Core Requirement
Send messages to **unknown phone numbers** (drivers) and receive their responses without them having to add us first.

---

## Key Features Needed

### 1. Outbound Messaging
- Send messages to **any Indian mobile number** (+91)
- No need for recipient to save our number first
- Support for **template messages** (for first contact)

### 2. Interactive Messages
- **Two-step conversation flow:**
  1. Ask for Advance Amount (user replies with number)
  2. Ask for Quantity (user replies with number)
- Validate user responses (numbers only)
- Send confirmation after completion

### 3. Webhook Integration
- **Webhook URL** to receive incoming messages
- Real-time delivery to our server
- Must work with our Flask backend (Python)

### 4. Message Format
```
📋 Vehicle Hire Confirmation
Manifest No: ARAK2508388

💰 Please enter Advance Amount
Example: 2000
```

---

## Technical Requirements

| Requirement | Details |
|-------------|---------|
| API Type | WhatsApp Business API (Cloud API preferred) |
| Webhook | HTTPS endpoint on our server |
| Message Types | Text, Template messages |
| Volume | ~50-100 messages/day initially |
| Number Type | Indian mobile numbers only |

---

## Questions for Askeva

1. Can we send to numbers who haven't messaged us first?
2. What's the cost per message?
3. How to set up webhook for incoming messages?
4. Template approval process and timeline?
5. Any rate limits?
6. Setup time?
