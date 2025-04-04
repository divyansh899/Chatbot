#!/usr/bin/env python3

import re
import sys

# Read the file
with open('user_bot.py', 'r') as f:
    lines = f.readlines()

# Fix indentation for the problematic lines
lines[6187] = '                            # Update user state with new step\n'
lines[6188] = '                            tmp_state = user_states[user_id].copy()\n'
lines[6189] = '                            tmp_state["step"] = "waiting_for_2fa"\n'
lines[6190] = '                            set_user_state(user_id, tmp_state)\n'

# Write the file back
with open('user_bot.py', 'w') as f:
    f.writelines(lines)

print("Fixed indentation in user_bot.py") 