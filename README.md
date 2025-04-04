# OTPGod: Virtual Number Sales & OTP Forwarding Chatbot

A Node.js application that provides a chatbot interface for selling virtual phone numbers for Telegram and WhatsApp from different countries with manual payment verification and automatic OTP forwarding.

## Features

- Telegram bot integration with an interactive UI
- Virtual number assignment system for OTP verification
- Automatic OTP detection and forwarding to users
- Step-by-step guided purchasing process
- Support for multiple countries (India, Bangladesh, USA, and others)
- Different pricing based on country
- Virtual numbers for both Telegram and WhatsApp
- Manual payment process with UPI and Bank Transfer options
- OTP verification system for payment confirmation
- User authentication and order management
- RESTful API for integration with other platforms

## Technical Stack

- **Backend**: Node.js, Express.js
- **Database**: MongoDB with Mongoose ODM
- **Authentication**: JWT (JSON Web Tokens)
- **External APIs**: Telegram Bot API, Twilio (for messaging capabilities)

## Installation and Setup

### Prerequisites

- Node.js (v12 or higher)
- MongoDB
- NPM or Yarn

### Getting Started

1. Clone the repository
   ```
   git clone https://github.com/yourusername/otpgod.git
   cd otpgod
   ```

2. Install dependencies
   ```
   # Install backend dependencies
   cd backend
   npm install
   ```

3. Environment Variables
   Create a `.env` file in the backend directory with the following variables:
   ```
   NODE_ENV=development
   PORT=5000
   MONGO_URI=mongodb://localhost:27017/otpgod_db
   JWT_SECRET=your_jwt_secret
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_API_ID=your_telegram_api_id
   TELEGRAM_API_HASH=your_telegram_api_hash
   ```

4. Seed the database with sample virtual numbers
   ```
   npm run seed
   ```

5. Start the server
   ```
   npm run dev
   ```

### Telegram Bot Setup

1. Create a new Telegram bot using BotFather
2. Set the name to "OTPGod"
3. Set the webhook URL to your server's endpoint:
   ```
   https://your-server.com/api/telegram/webhook
   ```
4. Use the provided bot token in your application

## OTP Forwarding System

OTPGod includes a sophisticated system for obtaining virtual numbers and forwarding OTPs:

1. User requests a virtual Telegram number through the bot
2. User uses this number for verification on a third-party service
3. When an OTP is sent to this number, OTPGod automatically detects and forwards it
4. User receives the OTP instantly in their Telegram chat

For detailed documentation on this feature, see [TELEGRAM_OTP_SYSTEM.md](TELEGRAM_OTP_SYSTEM.md).

## Manual Payment Process

The chatbot supports a manual payment verification process:

1. User selects a virtual number (platform and country)
2. User chooses payment method (UPI or Bank Transfer)
3. Bot provides payment details
4. User makes the payment and confirms in the chat
5. System generates an OTP for verification
6. User enters the OTP to complete the purchase

For detailed documentation on the payment process, see [MANUAL_PAYMENT_INSTRUCTIONS.md](MANUAL_PAYMENT_INSTRUCTIONS.md).

## API Endpoints

### Authentication
- `POST /api/users/register` - Register a new user
- `POST /api/users/login` - Login and get token

### Virtual Numbers
- `GET /api/numbers` - Get all available virtual numbers
- `GET /api/numbers/:id` - Get specific virtual number
- `POST /api/numbers` - Create a new virtual number (admin)

### Orders
- `POST /api/orders` - Create a new order
- `PUT /api/orders/:id/payment` - Update payment status
- `POST /api/orders/:id/otp/send` - Generate and send OTP for verification
- `POST /api/orders/:id/otp/verify` - Verify OTP and complete order
- `PUT /api/orders/:id/verify` - Admin endpoint to manually verify payments
- `GET /api/orders` - Get all user orders
- `GET /api/orders/:id` - Get specific order

### Telegram Bot
- `POST /api/telegram/start` - Start the bot conversation
- `POST /api/telegram/callback` - Handle bot callbacks
- `POST /api/telegram/message` - Handle text messages
- `POST /api/telegram/webhook` - Main webhook for Telegram updates

### Telegram Number Assignment
- `POST /api/telegram-numbers/assign` - Assign a number to a user
- `POST /api/telegram-numbers/release` - Release a number
- `GET /api/telegram-numbers/assigned/:userId` - Get user's assigned numbers
- `POST /api/telegram-numbers/monitor-otp` - Start monitoring for OTPs

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot and see welcome message |
| `/help` | View available commands and instructions |
| `/getnumber` | Request a new virtual Telegram number |
| `/mynumbers` | List all your assigned virtual numbers |
| `/monitor [number]` | Start OTP monitoring for a specific number |
| `/stop [number]` | Stop OTP monitoring for a specific number |
| `/release [number]` | Release a number back to the pool |

## Development

### Running Tests
```
npm test
```

### Contributing
Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

# Telegram Bot with WhatsApp Integration

This is a multi-service bot that provides phone number management and OTP monitoring for both Telegram and WhatsApp services.

## Project Structure

- **user_bot_main.py**: The main stable version of the code. Do not modify directly.
- **development/user_bot_dev.py**: Development version for testing new features.
- **backups/**: Contains dated backups of the code.

## How to Run

### Main Version

To run the main, stable version of the bot:

```bash
source venv/bin/activate
python user_bot_main.py
```

### Development Version

To work on new features, use the development version:

```bash
source venv/bin/activate
python development/user_bot_dev.py
```

## Development Workflow

1. Always make changes to the development version first
2. Test thoroughly before promoting to main
3. When ready to update the main version:
   ```bash
   # Create a backup of the current main version
   DATE=$(date "+%Y-%m-%d_%H-%M-%S")
   cp user_bot_main.py backups/user_bot_backup_$DATE.py
   
   # Update the main version
   cp development/user_bot_dev.py user_bot_main.py
   ```

## Database

The bot uses MongoDB. Before running the bot:

```bash
# Start MongoDB
mongod --dbpath ./fresh_db --port 27018
```

## Features

- Telegram number management
- WhatsApp number management
- OTP monitoring and forwarding
- Session management (import/export)
- Admin panel for user management
- Payment processing

## Admin Commands

- `/admin` - Access the admin panel
- `/exportstring [phone]` - Export session string
- `/addsession [phone] [session]` - Import session
- `/loginnumber [phone]` - Login a number
- `/deletesession [phone]` - Delete a session

## User Commands

- `/start` - Start the bot
- `/help` - Show help menu
- `/mynumbers` - View your numbers
- `/id` - Show your Telegram ID

## Helper Scripts

We've included several helper scripts to make working with the bot easier:

- **scripts/start_bot.sh**: Start MongoDB and the main bot
  ```bash
  ./scripts/start_bot.sh
  ```

- **scripts/stop_bot.sh**: Stop the bot and MongoDB
  ```bash
  ./scripts/stop_bot.sh
  ```

- **scripts/update_main.sh**: Safely update the main version from development
  ```bash
  ./scripts/update_main.sh
  ```

These scripts automate common tasks and help ensure that the proper procedures are followed for updating the main code. 