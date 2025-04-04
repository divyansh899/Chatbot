#!/usr/bin/env python3

# Read the file
with open('/Users/divyanshchugh/Desktop/chat bot/user_bot.py', 'r') as file:
    lines = file.readlines()

# Find the problematic section
for i in range(5045, 5055):
    if "Authentication code sent" in lines[i]:
        start_line = i
        break

# Define the corrected message
corrected_lines = [
    '            f"📱 Authentication code sent to {phone_number}\\n\\n"\n',
    '            "Please enter the code you received. You can:\\n"\n',
    '            "1. Simply send the code directly as a message (e.g., 12345), OR\\n"\n',
    '            "2. Use the command format: /entercode 12345\\n\\n"\n',
    '            "If you need to specify a 2FA password:\\n"\n',
    '            "/entercode 12345 your_password"\n',
]

# Replace the problematic lines
end_line = start_line + 6  # Assuming 6 lines total for the message
lines[start_line:end_line+1] = corrected_lines

# Write the modified content back to the file
with open('/Users/divyanshchugh/Desktop/chat bot/user_bot.py', 'w') as file:
    file.writelines(lines)

print(f"Successfully fixed OTP prompt message at lines {start_line}-{end_line}") 