from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from integrations.discord_notifier import DiscordNotifier

notifier = DiscordNotifier()
print("Webhook URL:", notifier.webhook_url)

success = notifier.send_message("📡 **Arcane Portal Test Message** - Checking webhook connectivity.")
print("Sent general message success:", success)

success_alert = notifier.send_test_alert()
print("Sent test alert success:", success_alert)
